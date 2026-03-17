import logging
import os

import boto3

logger = logging.getLogger()

REGION = os.environ["REGION"]

_EVENT_NAME_INDEX = "EventNameIndex"
_PK_SERVER_PREFIX = "SERVER#"
_SK_EVENT_PREFIX = "EVENT#"

dynamodb = boto3.resource("dynamodb", region_name=REGION)


def get_all_events_by_server(table):
    """Scan EventNameIndex to get all event records grouped by server_id -> [event_id]."""
    server_events = {}

    response = table.scan(IndexName=_EVENT_NAME_INDEX)
    for item in response.get("Items", []):
        server_id = item.get("server_id")
        event_id = item.get("event_id")
        if server_id and event_id:
            server_events.setdefault(server_id, []).append(event_id)

    while "LastEvaluatedKey" in response:
        response = table.scan(
            IndexName=_EVENT_NAME_INDEX,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            server_id = item.get("server_id")
            event_id = item.get("event_id")
            if server_id and event_id:
                server_events.setdefault(server_id, []).append(event_id)

    return server_events


def get_event_record(table, server_id, event_id):
    """Get the full event record from DynamoDB. Returns item dict or None."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    sk = f"{_SK_EVENT_PREFIX}{event_id}"
    response = table.get_item(Key={"PK": pk, "SK": sk})
    return response.get("Item")


def delete_event_record(table, server_id, event_id):
    """Delete event record from DynamoDB. Returns True on success."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    sk = f"{_SK_EVENT_PREFIX}{event_id}"
    try:
        table.delete_item(Key={"PK": pk, "SK": sk})
        logger.info(f"Deleted DynamoDB record for event {event_id} in server {server_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete DynamoDB record for event {event_id}: {e}")
        return False
