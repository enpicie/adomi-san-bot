import json
import logging
import os
import time

import boto3
import requests

import db
import discord_api

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
REGION = os.environ["REGION"]
STARTGG_OAUTH_SECRET_NAME = os.environ["STARTGG_OAUTH_SECRET_NAME"]

# Discord guild scheduled event statuses
# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
STATUS_COMPLETED = 3
STATUS_CANCELED = 4

_REFRESH_THRESHOLD_SECONDS = 24 * 60 * 60  # 24 hours
STARTGG_REFRESH_URL = "https://api.start.gg/oauth/refresh"

sqs = boto3.client("sqs", region_name=REGION)
secrets_client = boto3.client("secretsmanager", region_name=REGION)

_oauth_credentials: dict | None = None


def _get_oauth_credentials() -> dict:
    global _oauth_credentials
    if _oauth_credentials is None:
        response = secrets_client.get_secret_value(SecretId=STARTGG_OAUTH_SECRET_NAME)
        _oauth_credentials = json.loads(response["SecretString"])
    return _oauth_credentials


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


def cleanup_ended_event(table, server_id, event_id):
    """Queue role removals, delete Discord event, and delete DynamoDB record.
    Returns the event name on success, or None if the record was not found."""
    event_record = db.get_event_record(table, server_id, event_id)
    if not event_record:
        logger.warning(
            f"DynamoDB record not found for event {event_id} in server {server_id}, skipping cleanup"
        )
        return None

    participant_role = event_record.get("participant_role")
    checked_in = event_record.get("checked_in") or {}
    event_name = event_record.get("event_name") or event_id

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

    discord_api.delete_guild_event(server_id, event_id)
    time.sleep(0.5)  # Brief pause between Discord API calls to avoid rate limits

    db.delete_event_record(table, server_id, event_id)
    return event_name


def refresh_startgg_tokens(table):
    """Check all servers with start.gg OAuth tokens and refresh any expiring within 24 hours."""
    server_configs = db.get_all_server_configs_with_oauth(table)
    logger.info(f"Checking start.gg token refresh for {len(server_configs)} server(s)")

    credentials = _get_oauth_credentials()

    for config in server_configs:
        server_id = config.get("server_id")
        refresh_token = config.get("startgg_refresh_token")
        expires_at = config.get("startgg_token_expires_at")

        if not refresh_token or not expires_at:
            continue

        time_until_expiry = int(expires_at) - int(time.time())
        if time_until_expiry > _REFRESH_THRESHOLD_SECONDS:
            logger.info(f"Token for server {server_id} valid for {time_until_expiry}s, no refresh needed")
            continue

        logger.info(f"Token for server {server_id} expires in {time_until_expiry}s, refreshing")
        try:
            response = requests.post(
                STARTGG_REFRESH_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "scope": "user.identity tournament.manager",
                },
                timeout=10,
            )
            logger.info(f"Token refresh response for server {server_id}: {response.status_code} {response.text}")

            if not response.ok:
                logger.error(f"Token refresh failed for server {server_id}: {response.status_code} {response.text}")
                continue

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            new_expires_in = token_data.get("expires_in", 7 * 24 * 3600)

            if not new_access_token:
                logger.error(f"No access_token in refresh response for server {server_id}: {token_data}")
                continue

            new_expires_at = int(time.time()) + new_expires_in
            db.update_server_oauth_token(table, server_id, new_access_token, new_refresh_token, new_expires_at)
            logger.info(f"Refreshed start.gg OAuth token for server {server_id}, expires_at={new_expires_at}")

        except Exception as e:
            logger.error(f"Exception during token refresh for server {server_id}: {e}")


def handler(event, context):
    table = db.dynamodb.Table(DYNAMODB_TABLE_NAME)

    refresh_startgg_tokens(table)

    server_events = db.get_all_events_by_server(table)
    if not server_events:
        logger.info("No active events found in DynamoDB")
        return

    total_events = sum(len(ids) for ids in server_events.values())
    logger.info(f"Found {total_events} events across {len(server_events)} servers")

    for server_id, db_event_ids in server_events.items():
        discord_events = discord_api.get_guild_events(server_id)
        if discord_events is None:
            logger.error(f"Skipping server {server_id} due to Discord API failure")
            continue

        # Map discord event id -> status for events managed by this bot
        db_event_id_set = set(db_event_ids)
        discord_event_status = {
            e["id"]: e["status"] for e in discord_events if e["id"] in db_event_id_set
        }

        cleaned_up_event_names = []
        for event_id in db_event_ids:
            status = discord_event_status.get(event_id)
            if status in (STATUS_COMPLETED, STATUS_CANCELED):
                logger.info(
                    f"Event {event_id} in server {server_id} ended (status={status}), cleaning up"
                )
                event_name = cleanup_ended_event(table, server_id, event_id)
                if event_name:
                    cleaned_up_event_names.append(event_name)
            elif status is None:
                logger.warning(
                    f"Event {event_id} in server {server_id} not found in Discord — "
                    f"assuming event is over, cleaning up"
                )
                event_name = cleanup_ended_event(table, server_id, event_id)
                if event_name:
                    cleaned_up_event_names.append(event_name)
            else:
                logger.info(
                    f"Event {event_id} in server {server_id} still active (status={status}), no action needed"
                )

        if cleaned_up_event_names:
            server_config = db.get_server_config(table, server_id)
            notification_channel_id = server_config.get("notification_channel_id") if server_config else None
            if notification_channel_id:
                event_list = "\n".join(f"• {name}" for name in cleaned_up_event_names)
                count = len(cleaned_up_event_names)
                message = f"🧹 Cleaned up {count} ended event(s):\n{event_list}"
                ping_organizers = server_config.get("ping_organizers", False) if server_config else False
                if ping_organizers:
                    organizer_role = server_config.get("organizer_role") if server_config else None
                    if organizer_role:
                        message = f"<@&{organizer_role}> {message}"
                discord_api.send_channel_message(notification_channel_id, message)
            else:
                logger.info(f"No notification_channel_id configured for server {server_id}, skipping notification")
