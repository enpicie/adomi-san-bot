import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.event.timezone_helper import to_utc_iso
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from commands.schedule.schedule_helper import build_schedule_content, remove_matched_plans, sync_schedule
from database.models.schedule_plan import SchedulePlan
from database.models.server_config import ServerConfig


def post_schedule(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Posts or updates the tracked schedule message for this server."""
    server_id = event.get_server_id()

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    channel = event.get_command_input_value("channel")
    create_new = event.get_command_input_value("create_new_post") or False
    title = event.get_command_input_value("title") or "Upcoming Events"

    real_events = db_helper.get_full_events_for_server(server_id, aws_services.dynamodb_table)
    planned_events = db_helper.get_schedule_plans_for_server(server_id, aws_services.dynamodb_table)
    planned_events = remove_matched_plans(server_id, real_events, planned_events, aws_services.dynamodb_table)

    content = build_schedule_content(title, real_events, planned_events)

    existing_message_id = server_config.schedule_message_id
    existing_channel_id = server_config.schedule_channel_id
    should_create = create_new or not existing_message_id

    pk = db_helper.build_server_pk(server_id)

    if should_create:
        if not channel:
            return ResponseMessage(
                content="❌ A channel is required when creating a new schedule post."
            )
        message_id = discord_helper.send_channel_message(channel, content)
        if not message_id:
            return ResponseMessage(content="❌ Failed to send the schedule message to Discord.")

        aws_services.dynamodb_table.update_item(
            Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
            UpdateExpression=(
                f"SET {ServerConfig.Keys.SCHEDULE_CHANNEL_ID} = :ch, "
                f"{ServerConfig.Keys.SCHEDULE_MESSAGE_ID} = :mid"
            ),
            ExpressionAttributeValues={":ch": channel, ":mid": message_id},
        )
        return ResponseMessage(
            content=f"✅ Schedule posted in {message_helper.get_channel_mention(channel)}."
        )
    else:
        success = discord_helper.edit_channel_message(existing_channel_id, existing_message_id, content)
        if not success:
            return ResponseMessage(
                content=(
                    "❌ Failed to update the tracked schedule message. "
                    "It may have been deleted. Use `create_new_post: True` to post a new one."
                )
            )
        return ResponseMessage(
            content=f"✅ Schedule updated in {message_helper.get_channel_mention(existing_channel_id)}."
        )


def update_schedule(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Refreshes the tracked schedule message, optionally changing the title."""
    server_id = event.get_server_id()

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    if not server_config.schedule_message_id or not server_config.schedule_channel_id:
        return ResponseMessage(
            content="❌ No tracked schedule message found. Use `/schedule-post` to create one first."
        )

    new_title = event.get_command_input_value("new_title")
    sync_schedule(server_id, server_config, aws_services.dynamodb_table, title=new_title)
    return ResponseMessage(
        content=f"✅ Schedule updated in {message_helper.get_channel_mention(server_config.schedule_channel_id)}."
    )


def add_plan(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Adds a planned event placeholder to the schedule."""
    server_id = event.get_server_id()

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    name = event.get_command_input_value("name")
    start_time_input = event.get_command_input_value("start_time")
    timezone = event.get_command_input_value("timezone")
    event_link = event.get_command_input_value("event_link")

    start_time_utc = to_utc_iso(start_time_input, timezone)

    plan = SchedulePlan(
        plan_name=name,
        start_time=start_time_utc,
        event_link=event_link or None,
    )
    db_helper.put_schedule_plan(server_id, plan, aws_services.dynamodb_table)
    sync_schedule(server_id, server_config, aws_services.dynamodb_table)

    return ResponseMessage(content=f"✅ Planned event **{name}** added to the schedule.")


def clear_past_plans(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Removes all past events (real and planned) from the schedule and refreshes the message."""
    server_id = event.get_server_id()

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    from datetime import datetime, timezone as dt_timezone
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())

    planned_events = db_helper.get_schedule_plans_for_server(server_id, aws_services.dynamodb_table)
    past_plans = []
    for plan in planned_events:
        try:
            epoch = int(datetime.fromisoformat(plan.start_time.replace("Z", "+00:00")).timestamp())
        except Exception:
            continue
        if epoch < now_epoch:
            past_plans.append(plan)

    for plan in past_plans:
        db_helper.delete_schedule_plan(server_id, plan.plan_name, aws_services.dynamodb_table)

    past_real_names = db_helper.delete_past_real_events(server_id, aws_services.dynamodb_table)

    total = len(past_plans) + len(past_real_names)
    if total == 0:
        return ResponseMessage(content="ℹ️ No past events to clear.")

    sync_schedule(server_id, server_config, aws_services.dynamodb_table)

    all_names = [f"**{p.plan_name}**" for p in past_plans] + [f"**{n}**" for n in past_real_names]
    return ResponseMessage(content=f"✅ Removed {total} past event(s): {', '.join(all_names)}")


def remove_plan(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Removes a planned event placeholder from the schedule."""
    server_id = event.get_server_id()

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    plan_name = event.get_command_input_value("plan_name")
    db_helper.delete_schedule_plan(server_id, plan_name, aws_services.dynamodb_table)
    sync_schedule(server_id, server_config, aws_services.dynamodb_table)

    return ResponseMessage(content=f"✅ Planned event **{plan_name}** removed from the schedule.")
