import logging
import re
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import db
import discord_api

logger = logging.getLogger()

_DISCORD_TIMESTAMP_RE = re.compile(r"<t:(\d+):[^>]+>")


def _to_epoch(utc_iso: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"Could not parse timestamp {utc_iso!r} to epoch")
        return None


def _get_event_name_from_line(line: str) -> Optional[str]:
    if not line.startswith("- "):
        return None
    content = line[2:]
    if content.startswith("~~") and content.endswith("~~"):
        content = content[2:-2]
    elif content.startswith("_") and content.endswith("_"):
        content = content[1:-1]
    parts = content.rsplit(" - ", 1)
    if len(parts) < 2:
        return None
    display = parts[0]
    if display.startswith("[") and "](" in display:
        return display[1 : display.index("](")]
    return display


def strikethrough_schedule_event(server_config: dict, event_name: str) -> None:
    """Apply strikethrough to a specific event entry in the tracked schedule message."""
    schedule_message_id = server_config.get("schedule_message_id")
    schedule_channel_id = server_config.get("schedule_channel_id")
    if not schedule_message_id or not schedule_channel_id:
        return
    current = discord_api.get_channel_message(schedule_channel_id, schedule_message_id)
    if current is None:
        logger.warning(f"Could not fetch schedule message to strikethrough {event_name!r}")
        return
    lines = current.split("\n")
    new_lines = []
    updated = False
    for line in lines:
        if not updated and _get_event_name_from_line(line) == event_name:
            entry = line[2:]
            if not (entry.startswith("~~") and entry.endswith("~~")):
                if entry.startswith("_") and entry.endswith("_"):
                    entry = entry[1:-1]
                entry = f"~~{entry}~~"
                line = f"- {entry}"
            updated = True
        new_lines.append(line)
    if updated:
        success = discord_api.edit_channel_message(schedule_channel_id, schedule_message_id, "\n".join(new_lines))
        if not success:
            logger.warning(f"Failed to apply strikethrough for {event_name!r} in schedule")
    else:
        logger.info(f"Event {event_name!r} not found in schedule, no strikethrough applied")


def _build_schedule_content(title: str, real_events: list, planned_events: list) -> str:
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())

    items = []

    for e in real_events:
        epoch = _to_epoch(e.get("start_time")) if e.get("start_time") else None
        name = e.get("event_name") or "Unnamed Event"
        startgg_url = e.get("startgg_url")
        display_name = f"[{name}]({startgg_url})" if startgg_url else name
        timestamp = f"**<t:{epoch}:F>**" if epoch is not None else "**TBD**"
        is_past = epoch is not None and epoch < now_epoch
        items.append((epoch if epoch is not None else float("inf"), display_name, timestamp, is_past, False))

    for p in planned_events:
        epoch = _to_epoch(p.get("start_time")) if p.get("start_time") else None
        if epoch is not None and epoch < now_epoch:
            continue
        name = p.get("plan_name") or "Unnamed Plan"
        event_link = p.get("event_link")
        display_name = f"[{name}]({event_link})" if event_link else name
        timestamp = f"**<t:{epoch}:F>**" if epoch is not None else "**TBD**"
        items.append((epoch if epoch is not None else float("inf"), display_name, timestamp, False, True))

    items.sort(key=lambda x: x[0])

    lines = [f"# {title}", ""]
    if not items:
        lines.append("*No events.*")
    else:
        for _, display_name, timestamp, is_past, is_planned in items:
            entry = f"{display_name} - {timestamp}"
            if is_past:
                entry = f"~~{entry}~~"
            elif is_planned:
                entry = f"_{entry}_"
            lines.append(f"- {entry}")

    return "\n".join(lines)


def _extract_title(message_content: str) -> str:
    """Extract the title from the first line of a schedule message (format: '# Title')."""
    first_line = (message_content or "").split("\n")[0]
    if first_line.startswith("# "):
        return first_line[2:]
    return "Upcoming Events"


# NOTE: NOT currently wired into handler.py — planned full-sync feature; only
# strikethrough_schedule_event is invoked by the scheduled job today.
def sync_schedule_for_server(table, server_id: str, server_config: dict) -> None:
    """
    Removes past orphaned planned events, then regenerates and updates the tracked
    schedule message (with strikethrough for any events whose start time has passed).
    No-op if no schedule is configured.
    """
    if not server_config:
        return

    schedule_message_id = server_config.get("schedule_message_id")
    schedule_channel_id = server_config.get("schedule_channel_id")
    if not schedule_message_id or not schedule_channel_id:
        return

    current_content = discord_api.get_channel_message(schedule_channel_id, schedule_message_id)
    if current_content is None:
        logger.warning(f"Could not fetch schedule message for server {server_id}, skipping sync")
        return
    title = _extract_title(current_content)

    real_events = db.get_full_events_for_server(table, server_id)
    planned_events = db.get_schedule_plans_for_server(table, server_id)

    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())
    remaining_plans = []
    for plan in planned_events:
        plan_name = plan.get("plan_name") or ""
        epoch = _to_epoch(plan.get("start_time")) if plan.get("start_time") else None
        if epoch is not None and epoch < now_epoch:
            db.delete_schedule_plan(table, server_id, plan_name)
            logger.info(f"Removed past plan '{plan_name}' for server {server_id}")
            continue
        remaining_plans.append(plan)

    content = _build_schedule_content(title, real_events, remaining_plans)
    success = discord_api.edit_channel_message(schedule_channel_id, schedule_message_id, content)
    if success:
        logger.info(f"Updated schedule message for server {server_id}")
    else:
        logger.warning(f"Failed to update schedule message for server {server_id}")
        if success is None:
            notification_channel_id = server_config.get("notification_channel_id") if server_config else None
            if notification_channel_id:
                discord_api.send_permission_error_notification(
                    notification_channel_id,
                    schedule_channel_id,
                    organizer_role=server_config.get("organizer_role"),
                    ping_organizers=server_config.get("ping_organizers", False),
                )
