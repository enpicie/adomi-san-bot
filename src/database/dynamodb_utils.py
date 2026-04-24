from datetime import datetime, timezone as dt_timezone
from typing import List, Tuple

from boto3.dynamodb.conditions import Key, Attr
from mypy_boto3_dynamodb.service_resource import Table

import utils.adomin_messages as adomin_messages
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.league_data import LeagueData
from database.models.schedule_plan import SchedulePlan
from database.models.server_config import ServerConfig

PK_SERVER_PREFIX = "SERVER#"

def build_server_pk(server_id: str) -> str:
    return f"{PK_SERVER_PREFIX}{server_id}"

def get_server_config_or_fail(server_id: str, table: Table) -> ServerConfig | ResponseMessage:
    pk = build_server_pk(server_id)
    print(f"[db] GET CONFIG server={server_id}")
    response = table.get_item(Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG})
    existing_data = response.get("Item")
    if not existing_data:
        print(f"[db] -> not found CONFIG server={server_id}")
        return ResponseMessage(content=adomin_messages.SERVER_CONFIG_MISSING)
    print(f"[db] -> found CONFIG server={server_id}")
    return ServerConfig.from_dynamodb(existing_data)

EVENT_NAME_INDEX = "EventNameIndex"
LEAGUE_NAME_INDEX = "LeagueNameIndex"

def get_events_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query EventNameIndex and return list of (event_name, event_id) tuples."""
    print(f"[db] QUERY EVENTS server={server_id}")
    response = table.query(
        IndexName=EVENT_NAME_INDEX,
        KeyConditionExpression=Key(EventData.Keys.SERVER_ID).eq(server_id)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} event(s) found for server={server_id}")
    return [
        (item[EventData.Keys.EVENT_NAME], item[EventData.Keys.EVENT_ID])
        for item in items
    ]

def get_server_event_data_or_fail(server_id: str, event_id: str, table: Table) -> EventData | ResponseMessage:
    pk = build_server_pk(server_id)
    sk = EventData.Keys.SK_EVENT_PREFIX + event_id
    print(f"[db] GET EVENT server={server_id} event_id={event_id}")
    response = table.get_item(Key={"PK": pk, "SK": sk})
    existing_data = response.get("Item")
    if not existing_data:
        print(f"[db] -> not found EVENT server={server_id} event_id={event_id}")
        return ResponseMessage(content=adomin_messages.SERVER_EVENT_DATA_MISSING)
    print(f"[db] -> found EVENT server={server_id} event_id={event_id}")
    return EventData.from_dynamodb(existing_data)


def get_full_events_for_server(server_id: str, table: Table) -> List[EventData]:
    """Query all EVENT records for a server by PK + SK prefix and return as EventData objects."""
    pk = build_server_pk(server_id)
    print(f"[db] QUERY ALL EVENTS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} event(s) found for server={server_id}")
    return [EventData.from_dynamodb(item) for item in items]


def enable_reminders_for_server_events(server_id: str, table: Table) -> int:
    """Enable reminders on all events that don't already have them. Returns count updated."""
    pk = build_server_pk(server_id)
    print(f"[db] ENABLE REMINDERS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(EventData.Keys.SK_EVENT_PREFIX)
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
                "Key": {"PK": pk, "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
                "UpdateExpression": f"SET {EventData.Keys.SHOULD_POST_REMINDER} = :spr, {EventData.Keys.DID_POST_REMINDER} = :dpr",
                "ExpressionAttributeValues": {":spr": True, ":dpr": False},
            }
        })
    if transact_items:
        table.meta.client.transact_write_items(TransactItems=transact_items)
    print(f"[db] -> enabled reminders on {len(transact_items)} event(s) for server={server_id}")
    return len(transact_items)


def delete_past_real_events(server_id: str, table: Table) -> List[str]:
    """Delete all past EVENT records from DynamoDB. Returns list of deleted event names."""
    pk = build_server_pk(server_id)
    print(f"[db] DELETE PAST EVENTS server={server_id}")
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    now_epoch = int(datetime.now(dt_timezone.utc).timestamp())
    deleted_names = []
    for item in response.get("Items", []):
        start_time = item.get(EventData.Keys.START_TIME)
        if not start_time:
            continue
        try:
            epoch = int(datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp())
        except Exception:
            continue
        if epoch < now_epoch:
            event_id = item.get(EventData.Keys.EVENT_ID)
            table.delete_item(Key={"PK": pk, "SK": EventData.Keys.SK_EVENT_PREFIX + event_id})
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
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(SchedulePlan.Keys.SK_PLAN_PREFIX)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} plan(s) found for server={server_id}")
    return [SchedulePlan.from_dynamodb(item) for item in items]


def put_schedule_plan(server_id: str, plan: SchedulePlan, table: Table) -> None:
    """Upsert a SCHEDULE_PLAN record, keyed by normalized plan name."""
    pk = build_server_pk(server_id)
    sk = SchedulePlan.Keys.SK_PLAN_PREFIX + SchedulePlan.normalize_name(plan.plan_name)
    item = {
        "PK": pk,
        "SK": sk,
        SchedulePlan.Keys.PLAN_NAME: plan.plan_name,
        SchedulePlan.Keys.START_TIME: plan.start_time,
    }
    if plan.event_link:
        item[SchedulePlan.Keys.EVENT_LINK] = plan.event_link
    print(f"[db] PUT SCHEDULE_PLAN server={server_id} plan={plan.plan_name!r}")
    table.put_item(Item=item)
    print(f"[db] -> ok")


def delete_schedule_plan(server_id: str, plan_name: str, table: Table) -> None:
    """Delete a SCHEDULE_PLAN record by plan name (normalized for the key)."""
    pk = build_server_pk(server_id)
    sk = SchedulePlan.Keys.SK_PLAN_PREFIX + SchedulePlan.normalize_name(plan_name)
    print(f"[db] DELETE SCHEDULE_PLAN server={server_id} plan={plan_name!r}")
    table.delete_item(Key={"PK": pk, "SK": sk})
    print(f"[db] -> ok")


def get_leagues_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query LeagueNameIndex and return list of (league_name, league_id) tuples."""
    print(f"[db] QUERY LEAGUES server={server_id}")
    response = table.query(
        IndexName=LEAGUE_NAME_INDEX,
        KeyConditionExpression=Key(LeagueData.Keys.SERVER_ID).eq(server_id)
    )
    items = response.get("Items", [])
    print(f"[db] -> {len(items)} league(s) found for server={server_id}")
    return [
        (item[LeagueData.Keys.LEAGUE_NAME], item[LeagueData.Keys.LEAGUE_ID])
        for item in items
    ]


def get_server_league_data_or_fail(server_id: str, league_id: str, table: Table) -> LeagueData | ResponseMessage:
    pk = build_server_pk(server_id)
    sk = LeagueData.Keys.SK_LEAGUE_PREFIX + league_id
    print(f"[db] GET LEAGUE server={server_id} league_id={league_id}")
    response = table.get_item(Key={"PK": pk, "SK": sk})
    existing_data = response.get("Item")
    if not existing_data:
        print(f"[db] -> not found LEAGUE server={server_id} league_id={league_id}")
        return ResponseMessage(content=adomin_messages.SERVER_LEAGUE_DATA_MISSING)
    print(f"[db] -> found LEAGUE server={server_id} league_id={league_id}")
    return LeagueData.from_dynamodb(existing_data)
