from mypy_boto3_dynamodb.service_resource import Table

from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.server_config import ServerConfig

PK_SERVER_PREFIX = "SERVER#"

def build_server_pk(server_id: str) -> str:
    return f"{PK_SERVER_PREFIX}{server_id}"

def get_server_config_or_fail(server_id: str, table: Table) -> ServerConfig | ResponseMessage:
    pk = build_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set the organizer role there 👍"
        )
    return ServerConfig.from_dynamodb(existing_data)

def get_server_event_data_or_fail(server_id: str, table: Table) -> EventData | ResponseMessage:
    pk = build_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": EventData.Keys.SK_SERVER})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content="🙀 There is no server event data set up! Run `/setup-server` first to get started."
        )
    return EventData.from_dynamodb(existing_data)
