# MIRROR: src/commands/schedule/schedule_helper.py (sync_schedule / build_schedule_content)
# — keep in sync (independent Lambda packaging prevents imports).
import logging
import re
from datetime import datetime, timezone as dt_timezone

import db_helper
import worker_discord_api as discord_api

logger = logging.getLogger()

DEFAULT_SCHEDULE_TITLE = "Upcoming Events"
NO_EVENTS_LINE = "*No events.*"

_DISCORD_TIMESTAMP_RE = re.compile(r"<t:(\d+):[^>]+>")


def _to_epoch(utc_iso: str):
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"[schedule] Could not parse timestamp {utc_iso!r} to epoch")
        return None


def _extract_title(message_content: str) -> str:
    """Extract the title from the first line of a schedule message (format: '# Title')."""
    first_line = (message_content or "").split("\n")[0]
    return first_line[2:] if first_line.startswith("# ") else DEFAULT_SCHEDULE_TITLE


def build_schedule_content(title: str, real_events: list, planned_events: list) -> str:
    """Build the full schedule message from event and plan records, sorted by start time."""
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
        lines.append(NO_EVENTS_LINE)
    else:
        for _, display_name, timestamp, is_past, is_planned in items:
            entry = f"{display_name} - {timestamp}"
            if is_past:
                entry = f"~~{entry}~~"
            elif is_planned:
                entry = f"_{entry}_"
            lines.append(f"- {entry}")

    return "\n".join(lines)


def _normalize_name(name: str) -> str:
    """MIRROR: SchedulePlan.normalize_name — matching is trimmed and case-insensitive."""
    return (name or "").strip().lower()


def sync_schedule(server_id: str, server_config: dict, table) -> None:
    """Regenerate the tracked schedule message from DynamoDB. No-op if none is tracked."""
    schedule_message_id = (server_config or {}).get("schedule_message_id")
    schedule_channel_id = (server_config or {}).get("schedule_channel_id")
    if not schedule_message_id or not schedule_channel_id:
        return

    # MIRROR: src sync_schedule — an unreadable message still gets rebuilt, under
    # the default title, rather than left stale.
    current_content = discord_api.get_channel_message(schedule_channel_id, schedule_message_id)
    if current_content is None:
        logger.warning(f"[schedule] Could not fetch schedule message for server {server_id}, using default title")
        title = DEFAULT_SCHEDULE_TITLE
    else:
        title = _extract_title(current_content)

    real_events = db_helper.get_full_events_for_server(server_id, table)
    planned_events = db_helper.get_schedule_plans_for_server(server_id, table)

    real_names = {_normalize_name(e.get("event_name")) for e in real_events}
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())
    remaining_plans = []
    for plan in planned_events:
        plan_name = plan.get("plan_name") or ""
        epoch = _to_epoch(plan.get("start_time")) if plan.get("start_time") else None
        superseded = _normalize_name(plan_name) in real_names
        if superseded or (epoch is not None and epoch < now_epoch):
            db_helper.delete_schedule_plan(server_id, plan_name, table)
            logger.info(f"[schedule] Removed plan {plan_name!r} for server {server_id}")
            continue
        remaining_plans.append(plan)

    content = build_schedule_content(title, real_events, remaining_plans)
    if not discord_api.edit_channel_message(schedule_channel_id, schedule_message_id, content):
        logger.warning(f"[schedule] Failed to update schedule message for server {server_id}")
