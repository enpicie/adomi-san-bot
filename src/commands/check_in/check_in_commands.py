from typing import Optional

import commands.check_in.check_in_constants as check_in_constants
import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
import commands.check_in.queue_role_removal as role_removal_queue
from aws_services import AWSServices
from database.models.event_data import EventData
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def _verify_has_organizer_role(event: DiscordEvent, aws_services: AWSServices) -> Optional[ResponseMessage]:
    """
    Wrapper to check if the calling user has the Organizer role to run relevant commands.
    Returns a ResponseMessage on failure (missing config or missing role), otherwise returns None.
    """
    config_result = db_helper.get_server_config_or_fail(event.get_server_id(), aws_services.dynamodb_table)
    if isinstance(config_result, ResponseMessage):
        return config_result
    needs_role_msg = permissions_helper.require_organizer_role(config_result, event)
    if needs_role_msg:
        return needs_role_msg
    # Implicit return None on success

def check_in_user(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Adds the user who invoked the command to the 'checked_in' map for the server's event record in DynamoDB.
    Assigns the participant role if configured.
    Returns a ResponseMessage indicating success or failure.
    """
    event_data_result = db_helper.get_server_event_data_or_fail(event.get_server_id(), aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.check_in_enabled:
        return ResponseMessage(
            content="😵‍💫 Check-ins are not being accepted right now.\n"
                    "An Organizer must start check-ins before I can accept any new ones."
        )

    user_id = event.get_user_id()
    if user_id in event_data_result.checked_in:
        existing_check_in = Participant.from_dynamodb(event_data_result.checked_in[user_id])
        return ResponseMessage(
            content=f"✅ You already checked in {existing_check_in.get_relative_time_added().lower()}."
        )

    checked_in_user = Participant(
        display_name=event.get_username(),
        user_id=user_id
    )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(event.get_server_id()), "SK": EventData.Keys.SK_SERVER},
        UpdateExpression=f"SET {EventData.Keys.CHECKED_IN}.#uid = :participant_info",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":participant_info": checked_in_user.to_dict()}
    )
    if event_data_result.participant_role:
        print(f"Assigning participant role {event_data_result.participant_role} to user {user_id}")
        discord_helper.add_role_to_user(
            guild_id=event.get_server_id(),
            user_id=user_id,
            role_id=event_data_result.participant_role
        )
    return ResponseMessage(
        content=f"✅ Checked in {message_helper.get_user_ping(user_id)}!"
    )

def show_checked_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Retrieves and displays a list of all currently checked-in users for the server event.
    Requires the calling user to have the organizer role.
    Returns a ResponseMessage with the list or an error/empty message.
    """
    error_message = _verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.checked_in:
        return ResponseMessage(
            content="🧐 There are currently no checked-in users."
        )

    content = message_helper.build_participants_list(
        list_header= "✅ **Checked-in Users:**",
        participants=list(event_data_result.checked_in.values())
    )

    return ResponseMessage(content=content).with_silent_pings()

def clear_checked_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Clears all checked-in users from the server event record in DynamoDB.
    Queues jobs to remove the participant role from all cleared users.
    Requires the calling user to have the organizer role.
    Returns a ResponseMessage indicating success or failure.
    """
    error_message = _verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.checked_in:
        return ResponseMessage(
            content="🧐 There are no checked-in users to clear."
        )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_SERVER},
        UpdateExpression=f"SET {EventData.Keys.CHECKED_IN} = :empty_map",
        ExpressionAttributeValues={":empty_map": {}}
    )
    content = "✅ All check-ins have been cleared"

    if event_data_result.participant_role:
        checked_in_users = list(event_data_result.checked_in.keys())
        role_removal_queue.enqueue_remove_role_jobs(
            server_id=server_id,
            user_ids=checked_in_users,
            role_id=event_data_result.participant_role,
            sqs_queue=aws_services.remove_role_sqs_queue
        )
        content += ", and I've queued up participant role removals 🫡"
    else:
        print("No participant_role set. No role to unsassign.")
        content += "!" # Distinctly end the content of message to return

    return ResponseMessage(content=content)

def _generate_participant_message(search_ids, source_dict, header, default_message):
    """
    Generates the message for list of participants in source_dict with ids in search list.
    Returns default message if no participants with an id in search_ids is found.
    """
    participants = [
        source_dict[user_id]
        for user_id in search_ids
    ]
    if participants:
        return message_helper.build_participants_list(
            list_header=header,
            participants=participants
        )
    else:
        return default_message

def show_not_checked_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = _verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    event_data_result = db_helper.get_server_event_data_or_fail(event.get_server_id(), aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    should_ping_users = event.get_command_input_value("ping_users") or False # Default to No ping

    registered_ids = event_data_result.registered.keys()
    checked_in_ids = event_data_result.checked_in.keys()

    # Get list of users registered but not checked-in
    not_checked_in_ids = set(registered_ids) - set(checked_in_ids)
    not_checked_in_message = _generate_participant_message(
        search_ids=not_checked_in_ids,
        source_dict=event_data_result.registered,
        header="🔍 **Participants not yet checked-in:**",
        default_message="✅ All registered participants have checked-in"
    )

    # Get list of users checked-in but not registered
    not_registered_ids = set(checked_in_ids) - set(registered_ids)
    not_registered_message = _generate_participant_message(
        search_ids=not_registered_ids,
        source_dict=event_data_result.checked_in,
        header="‼️ **Participants checked-in but not registered:**",
        default_message="👍 No unexpected check-ins"
    )

    content = f"{not_checked_in_message}\n{not_registered_message}"
    response = ResponseMessage(content)

    return response if should_ping_users else response.with_silent_pings()

def toggle_check_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = _verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    check_in_state = event.get_command_input_value("state")
    should_enable = True if check_in_state == check_in_constants.START_PARAM else False
    print(f"{EventData.Keys.CHECK_IN_ENABLED}: {should_enable} via input {check_in_state}")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(event.get_server_id()), "SK": EventData.Keys.SK_SERVER},
        UpdateExpression=f"SET {EventData.Keys.CHECK_IN_ENABLED} = :enable",
        ExpressionAttributeValues={":enable": should_enable}
    )
    content = (
        "🟢 Check-ins started! Participants can begin checking in with `/check-in`"
        if should_enable
        else "🔴 Check-ins closed! Check-ins will no longer be accepted."
    )

    return ResponseMessage(content=content)
