import logging
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import db
import discord_api

logger = logging.getLogger()


def _to_epoch(utc_iso: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return None


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
        name = p.get("plan_name") or "Unnamed Plan"
        event_link = p.get("event_link")
        display_name = f"[{name}]({event_link})" if event_link else name
        timestamp = f"**<t:{epoch}:F>**" if epoch is not None else "**TBD**"
        is_past = epoch is not None and epoch < now_epoch
        items.append((epoch if epoch is not None else float("inf"), display_name, timestamp, is_past, True))

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


def sync_schedule_for_server(table, server_id: str, server_config: dict) -> None:
    """
    Removes planned events whose names match a real event, then regenerates
    and updates the tracked schedule message. No-op if no schedule is configured.
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

    real_names = {(e.get("event_name") or "").strip().lower() for e in real_events}
    remaining_plans = []
    for plan in planned_events:
        plan_name = plan.get("plan_name") or ""
        if plan_name.strip().lower() in real_names:
            db.delete_schedule_plan(table, server_id, plan_name)
            logger.info(f"Removed matched plan '{plan_name}' for server {server_id}")
        else:
            remaining_plans.append(plan)

    content = _build_schedule_content(title, real_events, remaining_plans)
    success = discord_api.edit_channel_message(schedule_channel_id, schedule_message_id, content)
    if success:
        logger.info(f"Updated schedule message for server {server_id}")
    else:
        logger.warning(f"Failed to update schedule message for server {server_id}")
