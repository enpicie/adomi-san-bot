from datetime import datetime, timezone as dt_timezone
from typing import List, Optional

import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
from database.models.event_data import EventData
from database.models.schedule_plan import SchedulePlan
from database.models.server_config import ServerConfig


def _to_epoch(utc_iso: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return None


def build_schedule_content(
    title: str,
    real_events: List[EventData],
    planned_events: List[SchedulePlan],
) -> str:
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())

    items = []

    for e in real_events:
        epoch = _to_epoch(e.start_time) if e.start_time else None
        name = e.event_name or "Unnamed Event"
        display_name = f"[{name}]({e.startgg_url})" if e.startgg_url else name
        timestamp = f"**<t:{epoch}:F>**" if epoch is not None else "**TBD**"
        is_past = epoch is not None and epoch < now_epoch
        items.append((epoch if epoch is not None else float("inf"), display_name, timestamp, is_past, False))

    for p in planned_events:
        epoch = _to_epoch(p.start_time)
        display_name = f"[{p.plan_name}]({p.event_link})" if p.event_link else p.plan_name
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


def remove_matched_plans(
    server_id: str,
    real_events: List[EventData],
    planned_events: List[SchedulePlan],
    table,
) -> List[SchedulePlan]:
    """Delete any planned event whose normalized name matches a real event. Returns the pruned list."""
    real_names = {(e.event_name or "").strip().lower() for e in real_events}
    remaining = []
    for plan in planned_events:
        if SchedulePlan.normalize_name(plan.plan_name) in real_names:
            db_helper.delete_schedule_plan(server_id, plan.plan_name, table)
        else:
            remaining.append(plan)
    return remaining


def extract_title(message_content: str) -> str:
    """Extract the title from the first line of a schedule message (format: '# Title')."""
    first_line = (message_content or "").split("\n")[0]
    if first_line.startswith("# "):
        return first_line[2:]
    return "Upcoming Events"


def sync_schedule(server_id: str, server_config: ServerConfig, table, title: Optional[str] = None) -> None:
    """If a tracked schedule message exists, regenerate and update it. No-op otherwise.

    If title is not provided, it is extracted from the current message content.
    """
    if not server_config.schedule_message_id or not server_config.schedule_channel_id:
        return
    if title is None:
        current_content = discord_helper.get_channel_message(
            server_config.schedule_channel_id, server_config.schedule_message_id
        )
        title = extract_title(current_content) if current_content is not None else "Upcoming Events"
    real_events = db_helper.get_full_events_for_server(server_id, table)
    planned_events = db_helper.get_schedule_plans_for_server(server_id, table)
    planned_events = remove_matched_plans(server_id, real_events, planned_events, table)
    content = build_schedule_content(title, real_events, planned_events)
    success = discord_helper.edit_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id, content
    )
    if not success:
        print(f"[schedule] Failed to update schedule message for server {server_id}")
