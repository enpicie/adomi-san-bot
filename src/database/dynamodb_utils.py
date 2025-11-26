from mypy_boto3_dynamodb.service_resource import Table

import utils.adomin_messages as adomin_messages
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
            content=adomin_messages.SERVER_CONFIG_MISSING
        )
    print(f"Found {ServerConfig.Keys.SK_CONFIG} Record: {existing_data}")

    return ServerConfig.from_dynamodb(existing_data)

def get_server_event_data_or_fail(server_id: str, table: Table) -> EventData | ResponseMessage:
    pk = build_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": EventData.Keys.SK_SERVER})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content=adomin_messages.SERVER_EVENT_DATA_MISSING
        )
    print(f"Found {EventData.Keys.SK_SERVER} Record: {existing_data}")

    return EventData.from_dynamodb(existing_data)
