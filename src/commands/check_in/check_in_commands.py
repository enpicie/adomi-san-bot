from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import constants
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
import utils.discord_api_helper as discord_helper
import utils.message_helper as msg_helper
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def check_in_user(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Adds a user to the checked_in map for a channel record in DynamoDB.
    Returns a ResponseMessage indicating success or failure.
    """
    pk = db_helper.get_server_pk(event.get_server_id())
    sk = constants.SK_SERVER

    event_data = db_helper.get_server_event_data(event.get_server_id(), table)
    if not event_data:
        return ResponseMessage(
            content="🙀 Event data is not set up yet! Run `/setup-server` first to get started. "
        )
    participant_role = event_data.get(event_data_keys.PARTICIPANT_ROLE, "")

    display_name = event.get_username()
    user_id = event.get_user_id()
    checked_in_user = Participant(
        display_name=display_name,
        user_id=user_id
    )

    table.update_item(
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
