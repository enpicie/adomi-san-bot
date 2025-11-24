from botocore.exceptions import ClientError

import constants
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
import database.config_data_helper as config_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as msg_helper
import commands.check_in.queue_role_removal as role_removal_queue
from aws_services import AWSServices
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def check_in_user(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Adds a user to the checked_in map for a channel record in DynamoDB.
    Returns a ResponseMessage indicating success or failure.
    """
    table = aws_services.dynamotb_table
    pk = db_helper.get_server_pk(event.get_server_id())
    sk = constants.SK_SERVER

    event_data = db_helper.get_server_event_data(event.get_server_id(), table)
    if not event_data:
        return ResponseMessage(
            content="🙀 Event data is not set up yet! Run `/setup-server` first to get started."
        )
    participant_role = event_data.get(event_data_keys.PARTICIPANT_ROLE, "")

    display_name = event.get_username()
    user_id = event.get_user_id()
    checked_in_user = Participant(
        display_name=display_name,
        user_id=user_id
    )

    aws_services.dynamotb_table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET checked_in.#uid = :participant_info",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":participant_info": checked_in_user.to_dict()}
    )
    if participant_role:
        print(f"Assigning participant role {participant_role} to user {user_id}")
        discord_helper.add_role_to_user(
            guild_id=event.get_server_id(),
            user_id=user_id,
            role_id=participant_role
        )
    return ResponseMessage(
        content=f"✅ Checked in {msg_helper.get_user_ping(user_id)}!"
    )

def show_check_ins(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    table = aws_services.dynamotb_table
    server_id = event.get_server_id()

    event_data = db_helper.get_server_event_data(server_id, table)
    if not event_data:
        return ResponseMessage(
            content="🙀 There is no check-in data! Run `/setup-server` first to get started."
        )

    checked_in = event_data.get(event_data_keys.CHECKED_IN, {})
    if not checked_in:
        return ResponseMessage(
            content="ℹ️ There are currently no checked-in users."
        )

    content = (
        "✅ **Checked-in Users:**\n"
        + "\n".join(f"- {p['display_name']}" for p in checked_in.values())
    )

    return ResponseMessage(content=content)

def clear_check_ins(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Clears all checked-in users from the channel record in DynamoDB.
    Returns a ResponseMessage indicating success or failure.
    """
    table = aws_services.dynamotb_table
    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)
    sk = constants.SK_SERVER

    organizer_role = config_helper.try_get_organizer_role(server_id, table)
    if isinstance(organizer_role, ResponseMessage):
        return organizer_role # Directly return the error message

    if organizer_role not in event.get_user_roles():
        return ResponseMessage(
            content="❌ You don't have permission to clear check-ins. "
                    "Only users with the server's designated organizer role can do this."
        )

    event_data = db_helper.get_server_event_data(server_id, table)
    if not event_data:
        return ResponseMessage(
            content="🙀 There is no check-in data to clear! Run `/setup-server` first to get started."
        )
    participant_role = event_data.get(event_data_keys.PARTICIPANT_ROLE, "")
    checked_in = event_data.get(event_data_keys.CHECKED_IN, {})
    if not checked_in:
        return ResponseMessage(
            content="ℹ️ There are no checked-in users to clear."
        )
    checked_in_users = list(checked_in.keys())

    try:
        role_removal_queue.enqueue_remove_role_jobs(
            server_id=server_id,
            user_ids=checked_in_users,
            role_id=participant_role,
            sqs_queue=aws_services.remove_role_sqs_queue
        )
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET checked_in = :empty_map",
            ExpressionAttributeValues={":empty_map": {}}
        )
    except ClientError:
        raise

    return ResponseMessage(
        content="✅ All check-ins have been cleared, and I've queued up participant role removals 🫡"
    )
