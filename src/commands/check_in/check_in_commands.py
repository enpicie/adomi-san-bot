from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import constants
import database.dynamodb_helper as db_helper
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

    display_name = event.get_username()
    user_id = event.get_user_id()
    checked_in_user = Participant(
        display_name=display_name,
        user_id=user_id
    )

    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET checked_in.#uid = :participant_info",
            ExpressionAttributeNames={"#uid": user_id},
            ExpressionAttributeValues={":participant_info": checked_in_user.to_dict()},
            ConditionExpression="attribute_exists(PK)"  # Ensures the record exists
        )
        return ResponseMessage(
            content=f"✅ Checked in {msg_helper.get_user_ping(user_id)}!"
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return ResponseMessage(
                content=f"This server has not been set up yet! Run `/setup-server` so I can get set up to start working 🙏"
            )
        # Re-raise unexpected errors
        raise
