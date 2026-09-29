"""Deferred handlers for event commands whose work cannot finish inside Discord's
3-second interaction deadline.

`/event-create-startgg` pages the start.gg GraphQL API (up to 20 pages at a 10s
timeout each) before it creates anything, so the bot Lambda answers immediately
with a placeholder and this runs the real work.

MIRROR: src/commands/event/event_commands.py (create_event_startgg) and
src/commands/event/event_helper.py — keep in sync.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

import claims
import db_helper
import worker_discord_api as discord_api
import worker_schedule_sync as schedule_sync
import worker_startgg_api as startgg_api
import timezone_helper

logger = logging.getLogger()

# MIRROR: src/commands/event/event_commands.py NO_PARTICIPANT_ROLE_WARNING
NO_PARTICIPANT_ROLE_WARNING = (
    "\n⚠️ No participant role is set for this event. "
    "Use `/event-update` or `/set-default-participant-role` to add one."
)


def _to_discord_ts(utc_iso: str) -> str:
    epoch = schedule_sync._to_epoch(utc_iso)
    return f"<t:{epoch}:F>" if epoch is not None else f"`{utc_iso}`"


def _is_past_time(utc_iso: str) -> bool:
    try:
        return datetime.fromisoformat(utc_iso.replace("Z", "+00:00")) < datetime.now(dt_timezone.utc)
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"[event] Failed to parse timestamp {utc_iso!r}")
        return False


def _has_ended(event_item: dict) -> bool:
    """True if the event's end time has passed. Unparseable or absent end times
    count as still active so a duplicate is never missed on bad data."""
    end_time = event_item.get("end_time")
    if not end_time:
        return False
    try:
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        return end < datetime.now(dt_timezone.utc)
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"[event] Failed to parse end_time {end_time!r} while checking for duplicates")
        return False


def find_duplicate_event(server_id: str, table, event_name=None, start_time_utc=None, startgg_url=None):
    """Find an active event that a new event would duplicate. See the src twin."""
    new_slug = startgg_api.extract_startgg_slug(startgg_url) if startgg_url else None

    for existing in db_helper.get_full_events_for_server(server_id, table):
        if _has_ended(existing):
            continue
        existing_url = existing.get("startgg_url")
        if new_slug and existing_url:
            if startgg_api.extract_startgg_slug(existing_url) == new_slug:
                logger.info(f"[event] Duplicate by start.gg slug={new_slug!r} event_id={existing.get('event_id')}")
                return existing
        if event_name and existing.get("event_name") == event_name:
            if start_time_utc and existing.get("start_time") != start_time_utc:
                continue
            logger.info(f"[event] Duplicate by name={event_name!r} event_id={existing.get('event_id')}")
            return existing
    return None


def _duplicate_event_message(duplicate: dict) -> str:
    """Explain that an identical event already exists instead of creating a second one."""
    return (
        f"⚠️ **{duplicate.get('event_name')}** already exists on this server, so I didn't create a second one.\n"
        f"Use `/event-update-startgg` to change it, or `/event-delete` to remove it first."
    )


def _build_no_discord_report(no_discord_names: list) -> str:
    """MIRROR: src/commands/event/event_commands.py _build_no_discord_report."""
    if not no_discord_names:
        return ""
    participant_list_markdown = "\n".join([f"* {name}" for name in no_discord_names])
    return (
        "\n**I found these start.gg users do not have Discord linked**\n"
        "---\n"
        f"{participant_list_markdown}\n"
        "\n*Please ensure the correct Discord account is linked and set to public on their start.gg profile.*"
    )


def _persist_event(server_id: str, event_id: str, table, *, name, location, start_time_utc,
                   end_time_utc, description, participant_role, should_post_reminder,
                   startgg_url, registered) -> None:
    """MIRROR: event_helper.create_event_record's put_item plus create_event_startgg's
    follow-up update, collapsed into the single write this path needs."""
    item = {
        "PK": db_helper.event_key(server_id, event_id)["PK"],
        "SK": db_helper.event_key(server_id, event_id)["SK"],
        "server_id": server_id,
        "event_id": event_id,
        "event_name": name,
        "event_location": location,
        "start_time": start_time_utc,
        "end_time": end_time_utc,
        "participant_role": participant_role or "",
        "checked_in": {},
        "registered": registered or {},
        "queue": {},
        "check_in_enabled": False,
        "register_enabled": False,
        "should_post_reminder": should_post_reminder,
        "did_post_reminder": False,
        "startgg_url": startgg_url,
    }
    table.put_item(Item=item)
    logger.info(f"[event] Created event_id={event_id} name={name!r} server={server_id}")


def handle_event_create_startgg(event_body: dict, aws_services) -> str:
    """Create an event from a start.gg link and import its registered participants.

    Permissions and link validity are already checked by the bot Lambda before
    this is enqueued; everything here is the slow half.
    """
    table = aws_services.dynamodb_table
    server_id = event_body["guild_id"]
    event_url = db_helper.get_command_input(event_body, "event_link")

    server_config = db_helper.get_server_config(server_id, table)
    if not server_config:
        return db_helper.SERVER_CONFIG_MISSING

    startgg_event = startgg_api.query_startgg_event(event_url)

    if not startgg_event["start_time_utc"]:
        return (
            "😔 Could not retrieve the start time from this start.gg event. "
            "Please create the event manually with `/event-create`."
        )

    past_time_warning = ""
    start_time_utc = startgg_event["start_time_utc"]
    if _is_past_time(start_time_utc):
        original = start_time_utc
        start_time_utc = (datetime.now(dt_timezone.utc) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        past_time_warning = (
            f"\n⚠️ The start.gg event time ({_to_discord_ts(original)}) is in the past. "
            "The current time has been used instead."
        )

    participant_role = (
        db_helper.get_command_input(event_body, "participant_role")
        or server_config.get("default_participant_role")
    )
    no_role_warning = NO_PARTICIPANT_ROLE_WARNING if not participant_role else ""

    end_time_utc = timezone_helper.to_utc_iso(
        db_helper.get_command_input(event_body, "end_time"),
        db_helper.get_command_input(event_body, "timezone"),
    )
    event_name = db_helper.get_command_input(event_body, "event_name") or startgg_event["event_name"]

    # Re-check here as well as in the bot Lambda: SQS delivers at least once, and
    # the organizer may have submitted twice while the first was still queued.
    duplicate = find_duplicate_event(
        server_id, table, event_name=event_name, start_time_utc=start_time_utc, startgg_url=event_url
    )
    if duplicate:
        return _duplicate_event_message(duplicate)

    # Claimed before the Discord event exists: a lost claim means an identical
    # create is already in flight, and creating anyway would orphan a Discord event.
    identity = f"startgg:{startgg_api.extract_startgg_slug(event_url)}"
    if not claims.try_claim_event_create(server_id, identity, table):
        return f"⏳ I'm already creating **{event_name}** — no need to run it again."

    # The claim covers only this create's in-flight window. Released whether the
    # create succeeds or fails; after that, find_duplicate_event stops a repeat.
    try:
        # Checked again now the claim is held: closes the gap between another
        # delivery's put and its release, which the first check can miss.
        duplicate = find_duplicate_event(
            server_id, table, event_name=event_name, start_time_utc=start_time_utc, startgg_url=event_url
        )
        if duplicate:
            return _duplicate_event_message(duplicate)

        logger.info(f"[event] Creating event name={event_name!r} server={server_id}")
        try:
            event_id = discord_api.create_scheduled_event(
                server_id,
                name=event_name,
                location=startgg_event["location"],
                scheduled_start_time=start_time_utc,
                scheduled_end_time=end_time_utc,
                description=f"Register here: {event_url}",
            )
        except ValueError as e:
            # MIRROR: src/bot.py process_bot_command — a ValueError's text is the
            # organizer's message (e.g. Discord rejecting an end time before the start).
            logger.warning(f"[event] Discord rejected create server={server_id}: {e}")
            return str(e)

        registered = {p["user_id"]: p for p in startgg_event["participants"]}
        for p in startgg_event["no_discord_participants"]:
            registered[p["display_name"]] = p

        _persist_event(
            server_id, event_id, table,
            name=event_name,
            location=startgg_event["location"],
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            description=None,
            participant_role=participant_role,
            should_post_reminder=bool(server_config.get("should_always_remind")),
            startgg_url=event_url,
            registered=registered,
        )
    finally:
        claims.release_event_create_claim(server_id, identity, table)

    schedule_sync.sync_schedule(server_id, server_config, table)

    total_count = len(startgg_event["participants"]) + len(startgg_event["no_discord_participants"])
    no_discord_names = [p["display_name"] for p in startgg_event["no_discord_participants"]]
    no_discord_report = _build_no_discord_report(no_discord_names)

    return (
        f"✅ Event **{event_name}** created with {total_count} registered participants!"
        f"{past_time_warning}{no_discord_report}{no_role_warning}"
    )
