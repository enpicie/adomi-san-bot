import json
import logging
import os
import time

import boto3

import db
import discord_api

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
REGION = os.environ["REGION"]

# Discord guild scheduled event statuses
# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
STATUS_COMPLETED = 3
STATUS_CANCELED = 4

sqs = boto3.client("sqs", region_name=REGION)


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


def handler(event, context):
    table = db.dynamodb.Table(DYNAMODB_TABLE_NAME)

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
