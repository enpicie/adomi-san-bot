import json
import logging
import os
import time

import boto3

import db
import discord_api

logger = logging.getLogger()

_REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
_REGION = os.environ["REGION"]

_sqs = boto3.client("sqs", region_name=_REGION)


def _queue_role_removals(guild_id, checked_in, participant_role):
    """Queue SQS messages to remove participant role from all checked-in users.

    Iterates all users even on individual failures so every removal is attempted.
    """
    for user_id in checked_in:
        try:
            _sqs.send_message(
                QueueUrl=_REMOVE_ROLE_QUEUE_URL,
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
    """Queue role removals, delete Discord event, and mark DynamoDB record as ended.
    Returns the event name on success, or None if the record was not found or was already cleaned up."""
    event_record = db.get_event_record(table, server_id, event_id)
    if not event_record:
        logger.warning(
            f"DynamoDB record not found for event {event_id} in server {server_id}, skipping cleanup"
        )
        return None

    if event_record.get("is_ended"):
        logger.info(
            f"Event {event_id} in server {server_id} already marked as ended, skipping duplicate cleanup"
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
        _queue_role_removals(server_id, checked_in, participant_role)

    discord_api.delete_guild_event(server_id, event_id)
    time.sleep(0.5)  # Brief pause between Discord API calls to avoid rate limits

    claimed = db.mark_event_ended(table, server_id, event_id)
    if not claimed:
        logger.info(
            f"Event {event_id} in server {server_id} was concurrently cleaned up by another invocation"
        )
        return None
    return event_name
