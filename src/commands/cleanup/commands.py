from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import utils.message_helper as msg_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def delete_server(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Drops CONFIG server record for the current server
    """
    server_id = event.get_server_id
    pk = f"SERVER#{server_id}"
    sk = "CONFIG"

    try:
        with table.batch_writer() as batch:
            batch.delete_item(
                Key={"PK": pk, "SK": sk},
                # Ensures the record exists
                ConditionExpression="attribute_exists(PK)"
            )
        return ResponseMessage(
            content=f"Deleted config for server: {server_id}!"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return ResponseMessage(
                content=f"Not found: Server {server_id} does not exist."
            )
        # Re-raise unexpected errors
        raise
