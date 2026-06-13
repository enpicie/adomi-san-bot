# MIRROR: src/database/dynamodb_utils.py — keep in sync (independent Lambda packaging prevents imports).
# Plan-name normalization here is plan_name.strip().lower(), identical to
# SchedulePlan.normalize_name in src — keep both in sync if either changes.
import logging

import boto3
from boto3.dynamodb.conditions import Attr, Key

import scheduled_job_constants as constants

logger = logging.getLogger()

_EVENT_NAME_INDEX = "EventNameIndex"
_PK_SERVER_PREFIX = "SERVER#"
_SK_EVENT_PREFIX = "EVENT#"
_SK_CONFIG = "CONFIG"
_SK_PLAN_PREFIX = "SCHEDULE_PLAN#"

dynamodb = boto3.resource("dynamodb", region_name=constants.REGION)


def get_server_config(table, server_id):
    """Get the server CONFIG record. Returns item dict or None."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    response = table.get_item(Key={"PK": pk, "SK": _SK_CONFIG})
    return response.get("Item")


def get_all_events_by_server(table):
    """Scan EventNameIndex to get all event records grouped by server_id -> [event_id]."""
    server_events = {}

    scan_kwargs = {"IndexName": _EVENT_NAME_INDEX}
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            server_id = item.get("server_id")
            event_id = item.get("event_id")
            if server_id and event_id:
                server_events.setdefault(server_id, []).append(event_id)
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

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


def get_full_events_for_server(table, server_id):
    """Query all EVENT records for a server by PK + SK prefix. Returns list of item dicts."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(_SK_EVENT_PREFIX)
    )
    return response.get("Items", [])


def get_schedule_plans_for_server(table, server_id):
    """Query all SCHEDULE_PLAN records for a server. Returns list of item dicts."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(_SK_PLAN_PREFIX)
    )
    return response.get("Items", [])


def delete_schedule_plan(table, server_id, plan_name):
    """Delete a SCHEDULE_PLAN record by plan name (normalized for the key)."""
    pk = f"{_PK_SERVER_PREFIX}{server_id}"
    sk = _SK_PLAN_PREFIX + plan_name.strip().lower()
    table.delete_item(Key={"PK": pk, "SK": sk})


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


def mark_startgg_expiry_notified(table, server_id: str):
    """Flag that organizers have been notified about the start.gg token expiry, to avoid re-notifying every run."""
    table.update_item(
        Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": _SK_CONFIG},
        UpdateExpression="SET startgg_expiry_notified = :val",
        ExpressionAttributeValues={":val": True},
    )


def clear_startgg_expiry_notified(table, server_id: str):
    """Clear the start.gg expiry notification flag so a future expiry will notify again (e.g. after a re-link)."""
    table.update_item(
        Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": _SK_CONFIG},
        UpdateExpression="REMOVE startgg_expiry_notified",
    )
