import logging

import scheduled_job_constants as constants
import db
import discord_api
import event_cleanup
import event_reminders
import event_reschedule_check
import schedule_sync
import startgg_token_check

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Discord guild scheduled event statuses
# https://discord.com/developers/docs/resources/guild-scheduled-event#guild-scheduled-event-object-guild-scheduled-event-status
_STATUS_COMPLETED = 3
_STATUS_CANCELED = 4


def handler(event, context):
    """Scheduled Lambda entry point: checks start.gg token expiry, cleans up
    ended/removed Discord events, and sends event reminders for every server."""
    table = db.dynamodb.Table(constants.DYNAMODB_TABLE_NAME)

    try:
        startgg_token_check.check_startgg_tokens(table)
    except Exception as e:
        logger.error(f"Unhandled error during start.gg token expiry check: {e}")

    server_events = db.get_all_events_by_server(table)
    if not server_events:
        logger.info("No active events found in DynamoDB")
        return

    total_events = sum(len(ids) for ids in server_events.values())
    logger.info(f"Found {total_events} events across {len(server_events)} servers")

    for server_id, db_event_ids in server_events.items():
        server_config = db.get_server_config(table, server_id)

        discord_events = discord_api.get_guild_events(server_id)
        if discord_events is None:
            logger.error(f"Skipping server {server_id} due to Discord API failure")
            notification_channel_id = server_config.get("notification_channel_id") if server_config else None
            if notification_channel_id:
                discord_api.send_organizer_notification(
                    notification_channel_id,
                    "⚠️ Adomin failed to fetch Discord events for this server. Event reminders and cleanup may be delayed.",
                    organizer_role=server_config.get("organizer_role"),
                    ping_organizers=server_config.get("ping_organizers", False),
                )
            continue

        # Map discord event id -> status for events managed by this bot
        db_event_id_set = set(db_event_ids)
        discord_event_status = {
            e["id"]: e["status"] for e in discord_events if e["id"] in db_event_id_set
        }

        cleaned_up_event_names = []
        for event_id in db_event_ids:
            status = discord_event_status.get(event_id)
            if status in (_STATUS_COMPLETED, _STATUS_CANCELED) or status is None:
                if status is None:
                    logger.info(
                        f"Event {event_id} in server {server_id} not found in Discord, cleaning up"
                    )
                else:
                    logger.info(
                        f"Event {event_id} in server {server_id} ended (status={status}), cleaning up"
                    )
                event_name = event_cleanup.cleanup_ended_event(table, server_id, event_id, server_config)
                if event_name:
                    cleaned_up_event_names.append(event_name)
                    if server_config:
                        schedule_sync.strikethrough_schedule_event(server_config, event_name)
            else:
                logger.info(
                    f"Event {event_id} in server {server_id} still active (status={status}), checking reminders"
                )
                event_reminders.check_and_send_reminder(table, server_id, event_id, server_config)
                # Scout start.gg for a reschedule and alert organizers. Guarded: start.gg is an
                # external dependency, and a failure here must not block cleanup/reminders elsewhere.
                try:
                    event_reschedule_check.check_for_reschedule(table, server_id, event_id, server_config)
                except Exception as e:
                    logger.error(f"Reschedule check failed for event {event_id} in server {server_id}: {e}")

        if cleaned_up_event_names:
            notification_channel_id = server_config.get("notification_channel_id") if server_config else None
            if notification_channel_id:
                event_list = "\n".join(f"• {name}" for name in cleaned_up_event_names)
                count = len(cleaned_up_event_names)
                message = f"🧹 Cleaned up {count} ended event(s):\n{event_list}"
                result = discord_api.send_channel_message(notification_channel_id, message)
                if result is None:
                    logger.error(
                        f"Adomin is missing permissions to send to notification channel "
                        f"{notification_channel_id} in server {server_id}"
                    )
            else:
                logger.info(f"No notification_channel_id configured for server {server_id}, skipping notification")
