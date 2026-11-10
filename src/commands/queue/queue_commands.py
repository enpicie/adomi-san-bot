import commands.queue.queue_constants as queue_constants
import commands.queue.queue_helper as queue_helper
import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def _get_event_or_fail(event: DiscordEvent, aws_services: AWSServices) -> tuple[EventData, dict] | ResponseMessage:
    """Returns the command's event and its DynamoDB key, or the lookup's error message."""
    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    key = db_helper.build_event_key(server_id, event_data_result.event_id or event_id)
    return event_data_result, key


def join_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Adds the calling user to the back of an event's queue. A repeat join just reports their spot."""
    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_user_id()
    current_queue = event_data.queue or {}
    position = queue_helper.get_position(current_queue, user_id)
    if position is not None:
        return ResponseMessage(
            content=f"👍 You're already **#{position}** of {len(current_queue)} in the **{event_data.event_name}** queue."
        )

    if not event_data.queue_enabled:
        return ResponseMessage(
            content=f"😵‍💫 The queue for **{event_data.event_name}** is closed right now.\n"
                    "An Organizer must open the queue before you can join."
        )

    table = aws_services.dynamodb_table
    queue_helper.ensure_queue_map(table, key, event_data)
    updated_queue = queue_helper.join_queue(table, key, user_id, event.get_username())
    if updated_queue is None:  # A double-submitted join landed first
        return ResponseMessage(content=f"👍 You're already in the **{event_data.event_name}** queue.")

    position = queue_helper.get_position(updated_queue, user_id)
    print(f"[queue] JOIN user={user_id} position={position} {key['SK']}")
    return ResponseMessage(
        content=f"✅ You're in! You're **#{position}** of {len(updated_queue)} in the **{event_data.event_name}** queue."
    )


def leave_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Removes the calling user from an event's queue. Works while the queue is closed."""
    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_user_id()
    if user_id not in (event_data.queue or {}) or not queue_helper.remove_from_queue(aws_services.dynamodb_table, key, user_id):
        return ResponseMessage(content=f"🧐 You're not in the **{event_data.event_name}** queue.")

    print(f"[queue] LEAVE user={user_id} {key['SK']}")
    return ResponseMessage(content=f"👋 You've left the **{event_data.event_name}** queue.")


def view_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Shows an event's queue in order. Silent by default; pinging the queue is Organizer only."""
    should_ping_users = event.get_command_input_value("ping_users") or False  # Default to No ping
    if should_ping_users:
        error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
        if error_message:
            return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, _ = result

    current_queue = event_data.queue or {}
    status = "🟢 open" if event_data.queue_enabled else "🔴 closed"
    if not current_queue:
        return ResponseMessage(content=f"🧐 The **{event_data.event_name}** queue is empty ({status}).")

    header = f"📋 **{event_data.event_name} Queue** — {len(current_queue)} in queue ({status})"
    response = ResponseMessage(content=queue_helper.build_queue_list(header, current_queue))
    return response if should_ping_users else response.with_silent_pings()


def toggle_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Opens or closes joining an event's queue based on the 'state' input. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    _, key = result

    queue_state = event.get_command_input_value("state")
    should_enable = queue_state == queue_constants.START_PARAM
    print(f"[queue] {EventData.Keys.QUEUE_ENABLED}: {should_enable} via input {queue_state}")

    aws_services.dynamodb_table.update_item(
        Key=key,
        UpdateExpression=f"SET {EventData.Keys.QUEUE_ENABLED} = :enable",
        ExpressionAttributeValues={":enable": should_enable}
    )

    content = (
        "🟢 Queue open! Players can join with `/queue-join`"
        if should_enable
        else "🔴 Queue closed! No one new can join. Everyone already in the queue keeps their spot."
    )
    return ResponseMessage(content=content)


def pop_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Takes users off the front of an event's queue and pings them. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    count = event.get_command_input_value("count")
    if count is None:
        count = queue_constants.DEFAULT_POP_COUNT
    if count < 1 or count > queue_constants.MAX_POP_COUNT:
        return ResponseMessage(content=f"⚠️ Count must be between 1 and {queue_constants.MAX_POP_COUNT}.")

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    current_queue = event_data.queue or {}
    if not current_queue:
        return ResponseMessage(content=f"🧐 The **{event_data.event_name}** queue is empty.")

    popped = queue_helper.pop_queue(aws_services.dynamodb_table, key, current_queue, count)
    if not popped:
        return ResponseMessage(content="⚠️ The queue changed while popping. Please try again.")

    remaining = max(len(current_queue) - len(popped), 0)
    print(f"[queue] POP users={popped} remaining={remaining} {key['SK']}")
    mentions = ", ".join(message_helper.get_user_ping(user_id) for user_id in popped)
    return ResponseMessage(
        content=f"🎮 You're up: {mentions}!\n{remaining} left in the **{event_data.event_name}** queue."
    )


def remove_from_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Removes a specific user from an event's queue. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_command_input_value("user")
    if user_id not in (event_data.queue or {}) or not queue_helper.remove_from_queue(aws_services.dynamodb_table, key, user_id):
        return ResponseMessage(
            content=f"⚠️ {message_helper.get_user_ping(user_id)} is not in the queue for this event."
        ).with_silent_pings()

    print(f"[queue] REMOVE user={user_id} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Removed {message_helper.get_user_ping(user_id)} from the **{event_data.event_name}** queue."
    ).with_silent_pings()


def clear_queue(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Empties an event's queue. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    if not event_data.queue:
        return ResponseMessage(content="🧐 The queue is already empty.")

    queue_helper.clear_queue(aws_services.dynamodb_table, key)
    print(f"[queue] CLEAR {key['SK']}")
    return ResponseMessage(content=f"✅ The **{event_data.event_name}** queue has been cleared.")
