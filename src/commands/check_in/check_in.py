from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import utils.message_helper as msg_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def check_in_user(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Adds a user to the checked_in map for a channel record in DynamoDB.
    Returns a ResponseMessage indicating success or failure.
    """
    user_id = event.get_user_id()
    username = event.get_username()

    pk = f"SERVER#{event.get_server_id()}"
    sk = f"CHANNEL#{event.get_channel_id()}"

    try:
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression="SET checked_in.#uid = :user_info",
            ExpressionAttributeNames={"#uid": user_id},
            ExpressionAttributeValues={":user_info": {"username": username}},
            ConditionExpression="attribute_exists(PK)"  # Ensures the record exists
        )
        return ResponseMessage(
            content=f"Checked in {msg_helper.get_user_ping(user_id)}!"
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return ResponseMessage(
                content=f"This channel has not been registered yet. Cannot check in {username}."
            )
        # Re-raise unexpected errors
        raise
