from dataclasses import dataclass
from typing import Optional

from mypy_boto3_dynamodb.service_resource import Table

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


def create_event_record(server_id: str, record: EventRecord, table: Table) -> str:
    """
    Creates a Discord scheduled event and persists it to DynamoDB.
    Returns the created event ID.
    Raises RuntimeError if the Discord API call fails.
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
    Raises RuntimeError if the Discord API call fails entirely.
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
        success = discord_helper.update_scheduled_event(server_id, event_id, params)
    except discord_helper.EventAlreadyActiveError:
        print(f"[event] Event is active, retrying without start_time event_id={event_id}")
        success = discord_helper.update_scheduled_event(server_id, event_id, params, skip_start_time=True)
        start_time_updated = False

    if not success:
        raise RuntimeError(f"Failed to update Discord scheduled event '{event_id}' for server '{server_id}'")

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
    Raises RuntimeError if the Discord API call fails.
    """
    print(f"[event] Deleting event_id={event_id} server={server_id}")
    success = discord_helper.delete_scheduled_event(server_id, event_id)
    if not success:
        raise RuntimeError(f"Failed to delete Discord scheduled event '{event_id}' for server '{server_id}'")

    print(f"[event] Removing DynamoDB record event_id={event_id} server={server_id}")
    table.delete_item(Key={
        "PK": db_helper.build_server_pk(server_id),
        "SK": EventData.Keys.SK_EVENT_PREFIX + event_id,
    })
    print(f"[event] Deleted event_id={event_id} server={server_id}")
