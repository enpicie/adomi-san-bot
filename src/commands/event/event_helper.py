from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from mypy_boto3_dynamodb.service_resource import Table

import commands.event.startgg.startgg_api as startgg_api
import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
from database.models.event_data import EventData
from utils.discord_api_helper import ScheduledEventParams


@dataclass
class EventRecord:
    name: str
    location: str
    start_time_utc: str       # UTC ISO 8601, e.g. "2026-03-19T19:30:00Z"
    end_time_utc: str         # UTC ISO 8601
    description: Optional[str] = None
    participant_role: Optional[str] = None
    should_post_reminder: Optional[bool] = False


def _has_ended(event_data: EventData) -> bool:
    """True if the event's end time is in the past. Unparseable/absent end times
    count as still active so a duplicate is never missed on a bad timestamp."""
    if not event_data.end_time:
        return False
    try:
        end = datetime.fromisoformat(event_data.end_time.replace("Z", "+00:00"))
        # A stored time without an offset compares as naive and would raise here,
        # so the comparison stays inside the guard (matching _is_past_time).
        return end < datetime.now(dt_timezone.utc)
    except (ValueError, AttributeError, TypeError):
        print(f"[event] Failed to parse end_time {event_data.end_time!r} while checking for duplicates")
        return False


def build_event_identity(
    event_name: Optional[str],
    start_time_utc: Optional[str],
    startgg_url: Optional[str] = None,
) -> str:
    """Build a stable identity for the event a create is about to make.

    Used to claim an in-flight creation, so it must be identical across two
    invocations of the same command and differ for genuinely different events.
    """
    slug = startgg_api.extract_startgg_slug(startgg_url) if startgg_url else None
    if slug:
        return f"startgg:{slug}"
    return f"name:{event_name}|{start_time_utc}"


def find_duplicate_event(
    server_id: str,
    table: Table,
    event_name: Optional[str] = None,
    start_time_utc: Optional[str] = None,
    startgg_url: Optional[str] = None,
) -> Optional[EventData]:
    """Find an active event that a new event would duplicate.

    Matches on the start.gg event slug first — the strongest signal, since the
    same bracket cannot legitimately back two events. Otherwise it takes an exact
    name match *at the same start time*: an organizer setting up a month of
    "Midweek Melting" in one sitting is creating real events, not repeating one.

    Events whose end time has passed are ignored, so a recurring weekly can reuse
    its name once the previous instance is over.

    :param server_id: Discord server the event would belong to.
    :param table: The DynamoDB table holding event records.
    :param event_name: Name the new event would be created with.
    :param start_time_utc: Start time the new event would be created with. When
                           absent, the name match falls back to name alone.
    :param startgg_url: start.gg link the new event would be created from.
    :return: The existing EventData it collides with, or None.
    """
    new_slug = startgg_api.extract_startgg_slug(startgg_url) if startgg_url else None

    for existing in db_helper.get_full_events_for_server(server_id, table):
        if _has_ended(existing):
            continue
        if new_slug and existing.startgg_url:
            if startgg_api.extract_startgg_slug(existing.startgg_url) == new_slug:
                print(f"[event] Duplicate by start.gg slug={new_slug!r} existing_event_id={existing.event_id}")
                return existing
        if event_name and existing.event_name == event_name:
            if start_time_utc and existing.start_time != start_time_utc:
                continue
            print(f"[event] Duplicate by name={event_name!r} existing_event_id={existing.event_id}")
            return existing
    return None


def create_event_record(server_id: str, record: EventRecord, table: Table) -> str:
    """
    Creates a Discord scheduled event and persists it to DynamoDB.
    Returns the created event ID.
    Raises ValueError with a user-facing message if Discord rejects the create.
    """
    print(f"[event] Creating event name={record.name!r} server={server_id}")
    event_id = discord_helper.create_scheduled_event(server_id, ScheduledEventParams(
        name=record.name,
        location=record.location,
        scheduled_start_time=record.start_time_utc,
        scheduled_end_time=record.end_time_utc,
        description=record.description
    ))
    if not event_id:  # pragma: no cover — ValueError raised by helper before this point
        raise RuntimeError(f"Failed to create Discord scheduled event for server '{server_id}'")

    print(f"[event] Persisting event_id={event_id} to DynamoDB server={server_id}")
    table.put_item(Item={
        "PK": db_helper.build_server_pk(server_id),
        "SK": EventData.Keys.SK_EVENT_PREFIX + event_id,
        EventData.Keys.SERVER_ID: server_id,
        EventData.Keys.EVENT_ID: event_id,
        EventData.Keys.EVENT_NAME: record.name,
        EventData.Keys.EVENT_LOCATION: record.location,
        EventData.Keys.START_TIME: record.start_time_utc,
        EventData.Keys.END_TIME: record.end_time_utc,
        EventData.Keys.PARTICIPANT_ROLE: record.participant_role or "",
        EventData.Keys.CHECKED_IN: {},
        EventData.Keys.REGISTERED: {},
        EventData.Keys.QUEUE: {},
        EventData.Keys.CHECK_IN_ENABLED: False,
        EventData.Keys.REGISTER_ENABLED: False,
        EventData.Keys.SCORES: {},
        EventData.Keys.SCORE_ENABLED: False,
        EventData.Keys.QUEUE_ENABLED: False,
        EventData.Keys.SHOULD_POST_REMINDER: record.should_post_reminder or False,
        EventData.Keys.DID_POST_REMINDER: False,
    })
    print(f"[event] Created event_id={event_id} name={record.name!r} server={server_id}")
    return event_id


def update_event_record(server_id: str, event_id: str, record: EventRecord, table: Table) -> bool:
    """
    Updates the Discord scheduled event and persists the new metadata to DynamoDB.
    Returns True if the start time was updated on Discord, False if the event was already active
    and the start time could not be changed (other fields still updated).
    Raises ValueError with a user-facing message if Discord rejects the update.
    """
    print(f"[event] Updating event_id={event_id} server={server_id}")
    params = ScheduledEventParams(
        name=record.name,
        location=record.location,
        scheduled_start_time=record.start_time_utc,
        scheduled_end_time=record.end_time_utc,
        description=record.description
    )
    start_time_updated = True
    try:
        discord_helper.update_scheduled_event(server_id, event_id, params)
    except discord_helper.EventAlreadyActiveError:
        print(f"[event] Event is active, retrying without start_time event_id={event_id}")
        discord_helper.update_scheduled_event(server_id, event_id, params, skip_start_time=True)
        start_time_updated = False

    print(f"[event] Persisting updated metadata to DynamoDB event_id={event_id} server={server_id}")
    table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=(
            f"SET {EventData.Keys.EVENT_NAME} = :name, "
            f"{EventData.Keys.EVENT_LOCATION} = :location, "
            f"{EventData.Keys.START_TIME} = :start_time, "
            f"{EventData.Keys.END_TIME} = :end_time, "
            f"{EventData.Keys.PARTICIPANT_ROLE} = :participant_role"
        ),
        ExpressionAttributeValues={
            ":name": record.name,
            ":location": record.location,
            ":start_time": record.start_time_utc,
            ":end_time": record.end_time_utc,
            ":participant_role": record.participant_role or "",
        }
    )
    print(f"[event] Updated event_id={event_id} start_time_updated={start_time_updated}")
    return start_time_updated


def delete_event_record(server_id: str, event_id: str, table: Table) -> None:
    """
    Deletes the Discord scheduled event and removes the DynamoDB record.
    Raises ValueError with a user-facing message if Discord rejects the delete.
    """
    print(f"[event] Deleting event_id={event_id} server={server_id}")
    discord_helper.delete_scheduled_event(server_id, event_id)

    print(f"[event] Removing DynamoDB record event_id={event_id} server={server_id}")
    table.delete_item(Key={
        "PK": db_helper.build_server_pk(server_id),
        "SK": EventData.Keys.SK_EVENT_PREFIX + event_id,
    })
    print(f"[event] Deleted event_id={event_id} server={server_id}")
