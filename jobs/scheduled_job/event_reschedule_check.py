import logging
from datetime import datetime, timezone

import db
import discord_api
import startgg_api

logger = logging.getLogger()


def _format_time(utc_iso):
    """Render a UTC ISO 8601 string as a Discord full timestamp, falling back to the raw value."""
    if not utc_iso:
        return "TBD"
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:F>"
    except (ValueError, AttributeError, TypeError):
        return f"`{utc_iso}`"


def _is_past_time(utc_iso):
    """Return True if the given UTC ISO 8601 time is before now.

    MIRROR: _is_past_time in src/commands/event/event_commands.py — keep in sync.
    """
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return dt < datetime.now(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return False


def check_for_reschedule(table, server_id, event_id, server_config):
    """Alert organizers when start.gg shows a different start time than the one stored on Discord.

    Alert-only: the bot does not auto-reschedule. Organizers run `/event-refresh-startgg` to apply,
    which shifts the end time with the start so the duration is preserved.

    De-duped via the event's `reschedule_alerted_start` field, which records the start.gg time we
    last alerted about. A standing drift therefore alerts only once; the alert re-arms automatically
    when start.gg moves to a *new* time, or clears once the event is refreshed to match start.gg.
    """
    event_record = db.get_event_record(table, server_id, event_id)
    if not event_record:
        return

    startgg_url = event_record.get("startgg_url")
    if not startgg_url:
        return

    startgg_start = startgg_api.get_event_start_time_utc(startgg_url)
    if not startgg_start:
        return

    stored_start = event_record.get("start_time")
    already_alerted = event_record.get("reschedule_alerted_start")

    # No drift — start.gg matches what we have. Clear any stale marker so a future change re-arms.
    if startgg_start == stored_start:
        if already_alerted:
            db.clear_reschedule_alerted(table, server_id, event_id)
        return

    # start.gg moved the start into the past — /event-refresh-startgg refuses to apply a past start
    # (mirrors the guard in src refresh_event_from_startgg), so alerting would be a dead end. This
    # also suppresses noise on events already underway, whose stored start is naturally in the past.
    if _is_past_time(startgg_start):
        return

    # Drift detected. Only alert once per distinct start.gg time so we don't re-notify every run.
    if already_alerted == startgg_start:
        return

    notification_channel_id = server_config.get("notification_channel_id") if server_config else None
    if not notification_channel_id:
        # Can't notify without a channel; leave the marker unset so we alert once one is configured.
        logger.info(
            f"No notification_channel_id for server {server_id}, cannot alert reschedule for event {event_id}"
        )
        return

    event_name = event_record.get("event_name") or event_id
    message = (
        f"🔔 **{event_name}** looks rescheduled on start.gg.\n"
        f"New start: {_format_time(startgg_start)} (was {_format_time(stored_start)}).\n"
        "Run `/event-refresh-startgg` to update the Discord event — the end time shifts with it, "
        "keeping the same duration."
    )
    discord_api.send_organizer_notification(
        notification_channel_id,
        message,
        organizer_role=server_config.get("organizer_role"),
        ping_organizers=server_config.get("ping_organizers", False),
    )
    db.mark_reschedule_alerted(table, server_id, event_id, startgg_start)
    logger.info(
        f"Alerted reschedule for event {event_id} in server {server_id}: {stored_start} -> {startgg_start}"
    )
