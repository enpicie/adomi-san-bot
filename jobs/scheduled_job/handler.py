import logging
import os

import db
import discord_api
from event_cleanup import cleanup_ended_event
from event_reminders import check_and_send_reminder
from schedule_sync import sync_schedule_for_server
from startgg_token_refresh import refresh_startgg_tokens

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

# Discord guild scheduled event statuses
# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
_STATUS_COMPLETED = 3
_STATUS_CANCELED = 4


def handler(event, context):
    table = db.dynamodb.Table(_DYNAMODB_TABLE_NAME)

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

        server_config = None  # loaded at most once per server, shared by reminder and cleanup logic
        cleaned_up_event_names = []
        for event_id in db_event_ids:
            status = discord_event_status.get(event_id)
            if status in (_STATUS_COMPLETED, _STATUS_CANCELED):
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
                    f"Event {event_id} in server {server_id} still active (status={status}), checking reminders"
                )
                server_config = check_and_send_reminder(table, server_id, event_id, server_config)

        if cleaned_up_event_names:
            if server_config is None:
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

        if server_config is None:
            server_config = db.get_server_config(table, server_id)
        sync_schedule_for_server(table, server_id, server_config)
