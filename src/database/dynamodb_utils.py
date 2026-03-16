from typing import List, Tuple

from boto3.dynamodb.conditions import Key
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

EVENT_NAME_INDEX = "EventNameIndex"

def get_events_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query EventNameIndex and return list of (event_name, event_id) tuples."""
    response = table.query(
        IndexName=EVENT_NAME_INDEX,
        KeyConditionExpression=Key(EventData.Keys.SERVER_ID).eq(server_id)
    )
    return [
        (item[EventData.Keys.EVENT_NAME], item[EventData.Keys.EVENT_ID])
        for item in response.get("Items", [])
    ]

def get_server_event_data_or_fail(server_id: str, event_id: str, table: Table) -> EventData | ResponseMessage:
    pk = build_server_pk(server_id)
    sk = EventData.Keys.SK_EVENT_PREFIX + event_id

    response = table.get_item(Key={"PK": pk, "SK": sk})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content=adomin_messages.SERVER_EVENT_DATA_MISSING
        )
    print(f"Found {sk} Record: {existing_data}")

    return EventData.from_dynamodb(existing_data)
