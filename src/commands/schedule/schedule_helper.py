import re
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


_DISCORD_TIMESTAMP_RE = re.compile(r"<t:(\d+):[^>]+>")


def _epoch_from_line(line: str) -> Optional[int]:
    m = _DISCORD_TIMESTAMP_RE.search(line)
    return int(m.group(1)) if m else None


def _get_event_name_from_line(line: str) -> Optional[str]:
    """Return the plain event name from a schedule entry line, or None if not an event line."""
    if not line.startswith("- "):
        return None
    content = line[2:]
    if content.startswith("~~") and content.endswith("~~"):
        content = content[2:-2]
    elif content.startswith("_") and content.endswith("_"):
        content = content[1:-1]
    # Split on last ' - ' to isolate display_name from timestamp
    parts = content.rsplit(" - ", 1)
    if len(parts) < 2:
        return None
    display = parts[0]
    if display.startswith("[") and "](" in display:
        return display[1 : display.index("](")]
    return display


def _line_has_event(line: str, event_name: str) -> bool:
    return _get_event_name_from_line(line) == event_name


def _build_event_line(event_name: str, epoch: Optional[int], startgg_url: Optional[str]) -> str:
    display_name = f"[{event_name}]({startgg_url})" if startgg_url else event_name
    timestamp = f"**<t:{epoch}:F>**" if epoch is not None else "**TBD**"
    return f"- {display_name} - {timestamp}"


def _insert_event_sorted(lines: list, new_line: str, epoch: Optional[int]) -> list:
    """Insert new_line into lines before the first event line with epoch >= new epoch."""
    new_key = epoch if epoch is not None else float("inf")
    for i, line in enumerate(lines):
        if not line.startswith("- "):
            continue
        cmp = _epoch_from_line(line)
        if cmp is None or cmp >= new_key:
            return lines[:i] + [new_line] + lines[i:]
    return lines + [new_line]


def _apply_no_events_placeholder(lines: list) -> list:
    """Ensure '*No events.*' appears iff no event lines remain."""
    has_events = any(l.startswith("- ") for l in lines)
    clean = [l for l in lines if l != "*No events.*"]
    if has_events:
        return clean
    insert_at = 2 if len(clean) >= 2 else len(clean)
    return clean[:insert_at] + ["*No events.*"] + clean[insert_at:]


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
        if epoch is not None and epoch < now_epoch:
            continue
        display_name = f"[{p.plan_name}]({p.event_link})" if p.event_link else p.plan_name
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


def strikethrough_schedule_event(server_config: ServerConfig, event_name: str) -> None:
    """Apply strikethrough to a specific event entry in the schedule. No-op if not tracked or not found."""
    if not server_config.schedule_message_id or not server_config.schedule_channel_id:
        return
    current = discord_helper.get_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id
    )
    if current is None:
        return
    lines = current.split("\n")
    new_lines = []
    updated = False
    for line in lines:
        if not updated and _line_has_event(line, event_name):
            entry = line[2:]
            if not (entry.startswith("~~") and entry.endswith("~~")):
                if entry.startswith("_") and entry.endswith("_"):
                    entry = entry[1:-1]
                entry = f"~~{entry}~~"
                line = f"- {entry}"
            updated = True
        new_lines.append(line)
    if updated:
        discord_helper.edit_channel_message(
            server_config.schedule_channel_id, server_config.schedule_message_id, "\n".join(new_lines)
        )


def remove_schedule_event(server_config: ServerConfig, event_name: str) -> None:
    """Remove a specific event entry from the schedule. No-op if not tracked or not found."""
    if not server_config.schedule_message_id or not server_config.schedule_channel_id:
        return
    current = discord_helper.get_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id
    )
    if current is None:
        return
    lines = current.split("\n")
    new_lines = [l for l in lines if not _line_has_event(l, event_name)]
    if len(new_lines) == len(lines):
        return
    new_lines = _apply_no_events_placeholder(new_lines)
    discord_helper.edit_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id, "\n".join(new_lines)
    )


def update_schedule_event(
    server_config: ServerConfig,
    old_name: str,
    new_name: str,
    new_start_time: Optional[str],
    new_startgg_url: Optional[str] = None,
) -> None:
    """Replace the schedule entry for old_name with a rebuilt line for new_name/time. No-op if not found."""
    if not server_config.schedule_message_id or not server_config.schedule_channel_id:
        return
    current = discord_helper.get_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id
    )
    if current is None:
        return
    epoch = _to_epoch(new_start_time) if new_start_time else None
    new_line = _build_event_line(new_name, epoch, new_startgg_url)
    lines = current.split("\n")
    without_old = [l for l in lines if not _line_has_event(l, old_name)]
    if len(without_old) == len(lines):
        return
    new_lines = _insert_event_sorted(without_old, new_line, epoch)
    discord_helper.edit_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id, "\n".join(new_lines)
    )


def _delete_past_plans(
    server_id: str,
    planned_events: List[SchedulePlan],
    table,
) -> List[SchedulePlan]:
    """Delete any planned event whose start_time is in the past. Returns the remaining list."""
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())
    remaining = []
    for plan in planned_events:
        epoch = _to_epoch(plan.start_time)
        if epoch is not None and epoch < now_epoch:
            db_helper.delete_schedule_plan(server_id, plan.plan_name, table)
        else:
            remaining.append(plan)
    return remaining


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
    planned_events = _delete_past_plans(server_id, planned_events, table)
    content = build_schedule_content(title, real_events, planned_events)
    success = discord_helper.edit_channel_message(
        server_config.schedule_channel_id, server_config.schedule_message_id, content
    )
    if not success:
        print(f"[schedule] Failed to update schedule message for server {server_id}")
