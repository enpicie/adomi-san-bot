from typing import Optional

import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
import commands.check_in.queue_role_removal as role_removal_queue
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.registered_participant import RegisteredParticipant

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

def show_registered(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
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
            content="ℹ️ There are currently no checked-in users."
        )

    content = (
        "✅ **Registered Users:**\n"
        + "\n".join(
            f"- {message_helper.get_user_ping(p[RegisteredParticipant.Keys.USER_ID])}"
            if p[RegisteredParticipant.Keys.USER_ID] != RegisteredParticipant.NO_DISCORD_ID_IDENTIFIER
            else f"- {p[RegisteredParticipant.Keys.DISPLAY_NAME]}" # Default to display_name when discord is not linked
            for p in event_data_result.registered.values()
        )
    )

    return ResponseMessage(content=content).with_silent_pings()

def clear_registered(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
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
            content="ℹ️ There are no checked-in users to clear."
        )

    checked_in_users = list(event_data_result.checked_in.keys())

    role_removal_queue.enqueue_remove_role_jobs(
        server_id=server_id,
        user_ids=checked_in_users,
        role_id=event_data_result.participant_role,
        sqs_queue=aws_services.remove_role_sqs_queue
    )

    if event_data_result.participant_role:
        aws_services.dynamodb_table.update_item(
            Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_SERVER},
            UpdateExpression="SET checked_in = :empty_map",
            ExpressionAttributeValues={":empty_map": {}}
        )
    else:
        print("No participant_role set. No role to unsassign.")

    return ResponseMessage(
        content="✅ All check-ins have been cleared, and I've queued up participant role removals 🫡"
    )
