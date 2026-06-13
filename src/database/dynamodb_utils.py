# MIRROR: jobs/scheduled_job/db.py — keep in sync (independent Lambda packaging prevents imports)
from datetime import datetime, timezone as dt_timezone
from typing import List, Optional, Tuple

from boto3.dynamodb.conditions import Key
from mypy_boto3_dynamodb.service_resource import Table

import utils.adomin_messages as adomin_messages
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.league_data import LeagueData
from database.models.schedule_plan import SchedulePlan
from database.models.server_config import ServerConfig

PK_SERVER_PREFIX = "SERVER#"
PK_ATTR = "PK"
SK_ATTR = "SK"

def build_server_pk(server_id: str) -> str:
    """Build the DynamoDB partition key value for a server's records."""
    return f"{PK_SERVER_PREFIX}{server_id}"

def build_event_key(server_id: str, event_id: str) -> dict:
    """Build the DynamoDB primary key dict for an EVENT record."""
    return {PK_ATTR: build_server_pk(server_id), SK_ATTR: EventData.Keys.SK_EVENT_PREFIX + event_id}

def get_server_config_or_fail(server_id: str, table: Table) -> ServerConfig | ResponseMessage:
    """Fetch the server's CONFIG record. Returns a ServerConfig on success,
    or a user-facing ResponseMessage if the server is not set up."""
    pk = build_server_pk(server_id)
    print(f"[db] GET CONFIG server={server_id}")
    response = table.get_item(Key={PK_ATTR: pk, SK_ATTR: ServerConfig.Keys.SK_CONFIG})
    config_record = response.get("Item")
    if not config_record:
        print(f"[db] -> not found CONFIG server={server_id}")
        return ResponseMessage(content=adomin_messages.SERVER_CONFIG_MISSING)
    print(f"[db] -> found CONFIG server={server_id}")
    return ServerConfig.from_dynamodb(config_record)

EVENT_NAME_INDEX = "EventNameIndex"
LEAGUE_NAME_INDEX = "LeagueNameIndex"

def _query_name_index(server_id: str, index_name: str, name_key: str, id_key: str, table: Table) -> List[Tuple[str, str]]:
    """Query a server-scoped name GSI and return (name, id) tuples.
    Both name indexes are partitioned by the server_id attribute."""
    response = table.query(
        IndexName=index_name,
        KeyConditionExpression=Key("server_id").eq(server_id)
    )
    return [
        (item[name_key], item[id_key])
        for item in response.get("Items", [])
    ]

def get_events_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query EventNameIndex and return list of (event_name, event_id) tuples for active (not ended) events."""
    print(f"[db] QUERY EVENTS server={server_id}")
    events = _query_name_index(server_id, EVENT_NAME_INDEX, EventData.Keys.EVENT_NAME, EventData.Keys.EVENT_ID, table)
    print(f"[db] -> {len(events)} active event(s) found for server={server_id}")
    return events

def _resolve_event_id(server_id: str, event_id: str, table: Table) -> str:
    # Discord may repopulate autocomplete fields with the display name instead of the snowflake ID.
    # Resolve by name first if the input isn't numeric.
    if not event_id.isdigit():
        events = get_events_for_server(server_id, table)
        resolved_id = next((candidate_event_id for name, candidate_event_id in events if name == event_id), None)
        if resolved_id:
            print(f"[db] -> resolved event by name {event_id!r} -> {resolved_id}")
            return resolved_id
    return event_id

def _get_server_record_or_fail(server_id: str, record_id: str, table: Table, resolve_record_id, sk_prefix: str,
                               record_label: str, id_label: str, not_found_message: str, model_class):
    """Resolve the record ID, fetch the record by PK/SK, and return it as a model
    instance — or a user-facing ResponseMessage if it doesn't exist."""
    record_id = resolve_record_id(server_id, record_id, table)
    pk = build_server_pk(server_id)
    print(f"[db] GET {record_label} server={server_id} {id_label}={record_id}")
    response = table.get_item(Key={PK_ATTR: pk, SK_ATTR: sk_prefix + record_id})
    record = response.get("Item")
    if not record:
        print(f"[db] -> not found {record_label} server={server_id} {id_label}={record_id}")
        return ResponseMessage(content=not_found_message)
    print(f"[db] -> found {record_label} server={server_id} {id_label}={record_id}")
    return model_class.from_dynamodb(record)

def get_server_event_data_or_fail(server_id: str, event_id: str, table: Table) -> EventData | ResponseMessage:
    """Fetch an EVENT record, resolving a display name back to its ID if needed.
    Returns an EventData on success, or a user-facing ResponseMessage if not found."""
    return _get_server_record_or_fail(
        server_id, event_id, table,
        resolve_record_id=_resolve_event_id,
        sk_prefix=EventData.Keys.SK_EVENT_PREFIX,
        record_label="EVENT",
        id_label="event_id",
        not_found_message=adomin_messages.SERVER_EVENT_DATA_MISSING,
        model_class=EventData,
    )


def get_full_events_for_server(server_id: str, table: Table) -> List[EventData]:
    """Query all EVENT records for a server by PK + SK prefix and return as EventData objects."""
    pk = build_server_pk(server_id)
    print(f"[db] QUERY ALL EVENTS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key(PK_ATTR).eq(pk) & Key(SK_ATTR).begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} event(s) found for server={server_id}")
    return [EventData.from_dynamodb(item) for item in items]


def enable_reminders_for_server_events(server_id: str, table: Table) -> int:
    """Enable reminders on all events that don't already have them. Returns count updated."""
    pk = build_server_pk(server_id)
    print(f"[db] ENABLE REMINDERS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key(PK_ATTR).eq(pk) & Key(SK_ATTR).begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    transact_items = []
    for item in response.get("Items", []):
        if item.get(EventData.Keys.SHOULD_POST_REMINDER):
            continue
        event_id = item.get(EventData.Keys.EVENT_ID)
        if not event_id:
            continue
        transact_items.append({
            "Update": {
                "TableName": table.name,
                "Key": build_event_key(server_id, event_id),
                "UpdateExpression": f"SET {EventData.Keys.SHOULD_POST_REMINDER} = :should_post_reminder, {EventData.Keys.DID_POST_REMINDER} = :did_post_reminder",
                "ExpressionAttributeValues": {":should_post_reminder": True, ":did_post_reminder": False},
            }
        })
    if transact_items:
        table.meta.client.transact_write_items(TransactItems=transact_items)
    print(f"[db] -> enabled reminders on {len(transact_items)} event(s) for server={server_id}")
    return len(transact_items)


def _parse_start_epoch(item: dict) -> Optional[int]:
    """Return the item's start_time as an epoch timestamp, or None if missing/unparseable."""
    start_time = item.get(EventData.Keys.START_TIME)
    if not start_time:
        return None
    try:
        return int(datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp())
    except Exception:
        print(f"[db] WARN unparseable start_time={start_time!r} for event_id={item.get(EventData.Keys.EVENT_ID)} — skipping")
        return None


def delete_past_real_events(server_id: str, table: Table) -> List[str]:
    """Delete all past EVENT records from DynamoDB. Returns list of deleted event names."""
    pk = build_server_pk(server_id)
    print(f"[db] DELETE PAST EVENTS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key(PK_ATTR).eq(pk) & Key(SK_ATTR).begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())
    deleted_names = []
    for item in response.get("Items", []):
        epoch = _parse_start_epoch(item)
        if epoch is None:
            continue
        if epoch < now_epoch:
            event_id = item.get(EventData.Keys.EVENT_ID)
            table.delete_item(Key=build_event_key(server_id, event_id))
            name = item.get(EventData.Keys.EVENT_NAME) or event_id
            print(f"[db] -> deleted past EVENT event_id={event_id} name={name!r}")
            deleted_names.append(name)
    print(f"[db] -> deleted {len(deleted_names)} past event(s) for server={server_id}")
    return deleted_names


def get_schedule_plans_for_server(server_id: str, table: Table) -> List[SchedulePlan]:
    """Return all SCHEDULE_PLAN records for a server."""
    pk = build_server_pk(server_id)
    print(f"[db] QUERY SCHEDULE_PLANS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key(PK_ATTR).eq(pk) & Key(SK_ATTR).begins_with(SchedulePlan.Keys.SK_PLAN_PREFIX)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} plan(s) found for server={server_id}")
    return [SchedulePlan.from_dynamodb(item) for item in items]


def put_schedule_plan(server_id: str, plan: SchedulePlan, table: Table) -> None:
    """Upsert a SCHEDULE_PLAN record, keyed by normalized plan name."""
    pk = build_server_pk(server_id)
    sk = SchedulePlan.Keys.SK_PLAN_PREFIX + SchedulePlan.normalize_name(plan.plan_name)
    item = {
        PK_ATTR: pk,
        SK_ATTR: sk,
        SchedulePlan.Keys.PLAN_NAME: plan.plan_name,
        SchedulePlan.Keys.START_TIME: plan.start_time,
    }
    if plan.event_link:
        item[SchedulePlan.Keys.EVENT_LINK] = plan.event_link
    print(f"[db] PUT SCHEDULE_PLAN server={server_id} plan={plan.plan_name!r}")
    table.put_item(Item=item)
    print("[db] -> ok")


def delete_schedule_plan(server_id: str, plan_name: str, table: Table) -> None:
    """Delete a SCHEDULE_PLAN record by plan name (normalized for the key)."""
    pk = build_server_pk(server_id)
    sk = SchedulePlan.Keys.SK_PLAN_PREFIX + SchedulePlan.normalize_name(plan_name)
    print(f"[db] DELETE SCHEDULE_PLAN server={server_id} plan={plan_name!r}")
    table.delete_item(Key={PK_ATTR: pk, SK_ATTR: sk})
    print("[db] -> ok")


def get_leagues_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query LeagueNameIndex and return list of (league_name, league_id) tuples."""
    print(f"[db] QUERY LEAGUES server={server_id}")
    leagues = _query_name_index(server_id, LEAGUE_NAME_INDEX, LeagueData.Keys.LEAGUE_NAME, LeagueData.Keys.LEAGUE_ID, table)
    print(f"[db] -> {len(leagues)} league(s) found for server={server_id}")
    return leagues


def _resolve_league_id(server_id: str, league_id: str, table: Table) -> str:
    # Discord may repopulate autocomplete fields with the display name instead of the short ID.
    # Resolve by name first if the input is longer than a valid league ID.
    if len(league_id) > LeagueData.LEAGUE_ID_MAX_LENGTH:
        leagues = get_leagues_for_server(server_id, table)
        resolved_id = next((candidate_league_id for name, candidate_league_id in leagues if name == league_id), None)
        if resolved_id:
            print(f"[db] -> resolved league by name {league_id!r} -> {resolved_id}")
            return resolved_id
    return league_id


def get_server_league_data_or_fail(server_id: str, league_id: str, table: Table) -> LeagueData | ResponseMessage:
    """Fetch a LEAGUE record, resolving a display name back to its ID if needed.
    Returns a LeagueData on success, or a user-facing ResponseMessage if not found."""
    return _get_server_record_or_fail(
        server_id, league_id, table,
        resolve_record_id=_resolve_league_id,
        sk_prefix=LeagueData.Keys.SK_LEAGUE_PREFIX,
        record_label="LEAGUE",
        id_label="league_id",
        not_found_message=adomin_messages.SERVER_LEAGUE_DATA_MISSING,
        model_class=LeagueData,
    )
