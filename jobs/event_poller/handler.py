import json
import logging
import os
import time

import boto3
import requests
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
REGION = os.environ["REGION"]

DISCORD_API = "https://discord.com/api/v10"
EVENT_NAME_INDEX = "EventNameIndex"
PK_SERVER_PREFIX = "SERVER#"
SK_EVENT_PREFIX = "EVENT#"

# Discord guild scheduled event statuses
# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
STATUS_COMPLETED = 3
STATUS_CANCELED = 4

dynamodb = boto3.resource("dynamodb", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)


def discord_request(method, url):
    while True:
        r = requests.request(method, url, headers={"Authorization": f"Bot {TOKEN}"})
        if r.status_code != 429:
            return r
        retry_after = r.json().get("retry_after", 1)
        logger.warning(f"Rate limited on {method} {url}, retrying after {retry_after}s")
        time.sleep(retry_after)


def get_all_events_by_server(table):
    """Scan EventNameIndex to get all event records grouped by server_id -> [event_id]."""
    server_events = {}

    response = table.scan(IndexName=EVENT_NAME_INDEX)
    for item in response.get("Items", []):
        server_id = item.get("server_id")
        event_id = item.get("event_id")
        if server_id and event_id:
            server_events.setdefault(server_id, []).append(event_id)

    while "LastEvaluatedKey" in response:
        response = table.scan(
            IndexName=EVENT_NAME_INDEX,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            server_id = item.get("server_id")
            event_id = item.get("event_id")
            if server_id and event_id:
                server_events.setdefault(server_id, []).append(event_id)

    return server_events


def get_discord_guild_events(guild_id):
    """Fetch all scheduled events for a guild from Discord API. Returns list or None on failure."""
    resp = discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/scheduled-events")
    if resp.status_code != 200:
        logger.error(
            f"Failed to fetch Discord events for guild {guild_id}: {resp.status_code} {resp.text}"
        )
        return None
    return resp.json()


def get_event_record(table, server_id, event_id):
    """Get the full event record from DynamoDB. Returns item dict or None."""
    pk = f"{PK_SERVER_PREFIX}{server_id}"
    sk = f"{SK_EVENT_PREFIX}{event_id}"
    response = table.get_item(Key={"PK": pk, "SK": sk})
    return response.get("Item")


def queue_role_removals(guild_id, checked_in, participant_role):
    """Queue SQS messages to remove participant role from all checked-in users.

    Iterates all users even on individual failures so every removal is attempted.
    """
    for user_id in checked_in:
        try:
            sqs.send_message(
                QueueUrl=REMOVE_ROLE_QUEUE_URL,
                MessageBody=json.dumps(
                    {
                        "guild_id": guild_id,
                        "user_id": user_id,
                        "role_id": participant_role,
                    }
                ),
            )
            logger.info(f"Queued role removal for user {user_id} in guild {guild_id}")
        except Exception as e:
            logger.error(
                f"Failed to queue role removal for user {user_id} in guild {guild_id}: {e}"
            )


def delete_discord_event(guild_id, event_id):
    """Delete a scheduled event from Discord. Returns True on success."""
    resp = discord_request(
        "DELETE", f"{DISCORD_API}/guilds/{guild_id}/scheduled-events/{event_id}"
    )
    if resp.status_code not in (200, 204):
        logger.error(
            f"Failed to delete Discord event {event_id} for guild {guild_id}: "
            f"{resp.status_code} {resp.text}"
        )
        return False
    return True


def delete_dynamodb_event(table, server_id, event_id):
    """Delete event record from DynamoDB. Returns True on success."""
    pk = f"{PK_SERVER_PREFIX}{server_id}"
    sk = f"{SK_EVENT_PREFIX}{event_id}"
    try:
        table.delete_item(Key={"PK": pk, "SK": sk})
        logger.info(f"Deleted DynamoDB record for event {event_id} in server {server_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete DynamoDB record for event {event_id}: {e}")
        return False


def cleanup_ended_event(table, server_id, event_id):
    """Queue role removals, delete Discord event, and delete DynamoDB record."""
    event_record = get_event_record(table, server_id, event_id)
    if not event_record:
        logger.warning(
            f"DynamoDB record not found for event {event_id} in server {server_id}, skipping cleanup"
        )
        return

    participant_role = event_record.get("participant_role")
    checked_in = event_record.get("checked_in") or {}

    logger.info(
        f"Event {event_id} cleanup: participant_role={participant_role!r}, "
        f"checked_in_count={len(checked_in)}, checked_in={list(checked_in)}"
    )

    if not participant_role:
        logger.warning(
            f"Event {event_id} in server {server_id} has no participant_role, skipping role removals"
        )
    elif not checked_in:
        logger.info(
            f"Event {event_id} in server {server_id} has no checked-in users, skipping role removals"
        )
    else:
        queue_role_removals(server_id, checked_in, participant_role)

    delete_discord_event(server_id, event_id)
    time.sleep(0.5)  # Brief pause between Discord API calls to avoid rate limits

    delete_dynamodb_event(table, server_id, event_id)


def handler(event, context):
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)

    server_events = get_all_events_by_server(table)
    if not server_events:
        logger.info("No active events found in DynamoDB")
        return

    total_events = sum(len(ids) for ids in server_events.values())
    logger.info(f"Found {total_events} events across {len(server_events)} servers")

    for server_id, db_event_ids in server_events.items():
        discord_events = get_discord_guild_events(server_id)
        if discord_events is None:
            logger.error(f"Skipping server {server_id} due to Discord API failure")
            continue

        # Map discord event id -> status for events managed by this bot
        db_event_id_set = set(db_event_ids)
        discord_event_status = {
            e["id"]: e["status"] for e in discord_events if e["id"] in db_event_id_set
        }

        for event_id in db_event_ids:
            status = discord_event_status.get(event_id)
            if status in (STATUS_COMPLETED, STATUS_CANCELED):
                logger.info(
                    f"Event {event_id} in server {server_id} ended (status={status}), cleaning up"
                )
                cleanup_ended_event(table, server_id, event_id)
            elif status is None:
                logger.warning(
                    f"Event {event_id} in server {server_id} not found in Discord — "
                    f"assuming event is over, cleaning up"
                )
                cleanup_ended_event(table, server_id, event_id)
            else:
                logger.info(
                    f"Event {event_id} in server {server_id} still active (status={status}), no action needed"
                )
