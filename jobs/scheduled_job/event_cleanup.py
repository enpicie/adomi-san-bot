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


def _queue_role_removals(guild_id, checked_in, participant_role, notification_channel_id=None, organizer_role=None, ping_organizers=False):
    """Queue SQS messages to remove participant role from all checked-in users.

    Iterates all users even on individual failures so every removal is attempted.
    Returns the number of users that failed to queue.
    """
    failures = 0
    for user_id in checked_in:
        try:
            payload = {
                "guild_id": guild_id,
                "user_id": user_id,
                "role_id": participant_role,
            }
            if notification_channel_id:
                payload["notification_channel_id"] = notification_channel_id
                payload["organizer_role"] = organizer_role
                payload["ping_organizers"] = ping_organizers
            _sqs.send_message(QueueUrl=_REMOVE_ROLE_QUEUE_URL, MessageBody=json.dumps(payload))
            logger.info(f"Queued role removal for user {user_id} in guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to queue role removal for user {user_id} in guild {guild_id}: {e}")
            failures += 1
    return failures


def cleanup_ended_event(table, server_id, event_id, server_config=None):
    """Queue role removals, delete the Discord event, and hard-delete the DynamoDB record.

    Returns the event name on success, or None if the record was already gone.
    """
    event_record = db.get_event_record(table, server_id, event_id)
    if not event_record:
        logger.info(f"Event {event_id} in server {server_id} already cleaned up, skipping")
        return None

    participant_role = event_record.get("participant_role")
    checked_in = event_record.get("checked_in") or {}
    event_name = event_record.get("event_name") or event_id

    logger.info(
        f"Event {event_id} ({event_name!r}) cleanup: participant_role={participant_role!r}, "
        f"checked_in_count={len(checked_in)}"
    )

    notification_channel_id = server_config.get("notification_channel_id") if server_config else None
    organizer_role = server_config.get("organizer_role") if server_config else None
    ping_organizers = server_config.get("ping_organizers", False) if server_config else False

    if not participant_role:
        logger.info(f"Event {event_id} in server {server_id} has no participant_role, skipping role removals")
    elif not checked_in:
        logger.info(f"Event {event_id} in server {server_id} has no checked-in users, skipping role removals")
    else:
        failures = _queue_role_removals(server_id, checked_in, participant_role, notification_channel_id, organizer_role, ping_organizers)
        if failures and notification_channel_id:
            discord_api.send_organizer_notification(
                notification_channel_id,
                f"⚠️ Failed to queue role removal for {failures} user(s) after event **{event_name}** ended. Their participant roles may need to be removed manually.",
                organizer_role=organizer_role,
                ping_organizers=ping_organizers,
            )

    discord_api.delete_guild_event(server_id, event_id)
    time.sleep(0.5)  # Brief pause between Discord API calls to avoid rate limits

    db.delete_event_record(table, server_id, event_id)
    logger.info(f"Event {event_id} ({event_name!r}) fully cleaned up for server {server_id}")
    return event_name
