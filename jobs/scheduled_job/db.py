import logging
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()

REGION = os.environ["REGION"]

_EVENT_NAME_INDEX = "EventNameIndex"
_PK_SERVER_PREFIX = "SERVER#"
_SK_EVENT_PREFIX = "EVENT#"
_SK_CONFIG = "CONFIG"

dynamodb = boto3.resource("dynamodb", region_name=REGION)


def get_server_config(table, server_id):
    """Get the server CONFIG record. Returns item dict or None."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    response = table.get_item(Key={"PK": pk, "SK": _SK_CONFIG})
    return response.get("Item")


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


def get_all_server_configs_with_oauth(table):
    """Scan for all server CONFIG records that have a startgg_refresh_token."""
    configs = []
    filter_expr = Attr("SK").eq(_SK_CONFIG) & Attr("startgg_refresh_token").exists()

    response = table.scan(FilterExpression=filter_expr)
    configs.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=filter_expr,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        configs.extend(response.get("Items", []))

    return configs


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


def mark_event_reminder_sent(table, server_id: str, event_id: str):
    """Set did_post_reminder to True on an event record to prevent duplicate reminder sends."""
    table.update_item(
        Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": f"{_SK_EVENT_PREFIX}{event_id}"},
        UpdateExpression="SET did_post_reminder = :val",
        ExpressionAttributeValues={":val": True}
    )


def update_server_oauth_token(table, server_id: str, access_token: str, refresh_token: str, expires_at: int):
    """Write a refreshed OAuth access token, refresh token, and expiry into the server's config record."""
    table.update_item(
        Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": _SK_CONFIG},
        UpdateExpression=(
            "SET oauth_token_startgg = :token, "
            "startgg_refresh_token = :refresh_token, "
            "startgg_token_expires_at = :expires_at"
        ),
        ExpressionAttributeValues={
            ":token": access_token,
            ":refresh_token": refresh_token,
            ":expires_at": expires_at,
        },
    )
