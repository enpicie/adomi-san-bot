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

    response = table.get_item(Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content=adomin_messages.SERVER_CONFIG_MISSING
        )
    print(f"Found {ServerConfig.Keys.SK_CONFIG} Record: {existing_data}")

    return ServerConfig.from_dynamodb(existing_data)

EVENT_NAME_INDEX = "EventNameIndex"
LEAGUE_NAME_INDEX = "LeagueNameIndex"

def get_events_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query EventNameIndex and return list of (event_name, event_id) tuples."""
    response = table.query(
        IndexName=EVENT_NAME_INDEX,
        KeyConditionExpression=Key(EventData.Keys.SERVER_ID).eq(server_id)
    )
    return [
        (item[EventData.Keys.EVENT_NAME], item[EventData.Keys.EVENT_ID])
        for item in response.get("Items", [])
    ]

def get_server_event_data_or_fail(server_id: str, event_id: str, table: Table) -> EventData | ResponseMessage:
    pk = build_server_pk(server_id)
    sk = EventData.Keys.SK_EVENT_PREFIX + event_id

    response = table.get_item(Key={"PK": pk, "SK": sk})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content=adomin_messages.SERVER_EVENT_DATA_MISSING
        )
    print(f"Found {sk} Record: {existing_data}")

    return EventData.from_dynamodb(existing_data)


def get_full_events_for_server(server_id: str, table: Table) -> List[EventData]:
    """Query all EVENT records for a server by PK + SK prefix and return as EventData objects."""
    pk = build_server_pk(server_id)
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(EventData.Keys.SK_EVENT_PREFIX)
    )
    return [EventData.from_dynamodb(item) for item in response.get("Items", [])]


def get_schedule_plans_for_server(server_id: str, table: Table) -> List[SchedulePlan]:
    """Return all SCHEDULE_PLAN records for a server."""
    pk = build_server_pk(server_id)
    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(SchedulePlan.Keys.SK_PLAN_PREFIX)
    )
    return [SchedulePlan.from_dynamodb(item) for item in response.get("Items", [])]


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
    table.put_item(Item=item)


def delete_schedule_plan(server_id: str, plan_name: str, table: Table) -> None:
    """Delete a SCHEDULE_PLAN record by plan name (normalized for the key)."""
    pk = build_server_pk(server_id)
    sk = SchedulePlan.Keys.SK_PLAN_PREFIX + SchedulePlan.normalize_name(plan_name)
    table.delete_item(Key={"PK": pk, "SK": sk})


def get_leagues_for_server(server_id: str, table: Table) -> List[Tuple[str, str]]:
    """Query LeagueNameIndex and return list of (league_name, league_id) tuples."""
    response = table.query(
        IndexName=LEAGUE_NAME_INDEX,
        KeyConditionExpression=Key(LeagueData.Keys.SERVER_ID).eq(server_id)
    )
    return [
        (item[LeagueData.Keys.LEAGUE_NAME], item[LeagueData.Keys.LEAGUE_ID])
        for item in response.get("Items", [])
    ]


def get_server_league_data_or_fail(server_id: str, league_id: str, table: Table) -> LeagueData | ResponseMessage:
    pk = build_server_pk(server_id)
    sk = LeagueData.Keys.SK_LEAGUE_PREFIX + league_id

    response = table.get_item(Key={"PK": pk, "SK": sk})
    existing_data = response.get("Item")
    if not existing_data:
        return ResponseMessage(
            content=adomin_messages.SERVER_LEAGUE_DATA_MISSING
        )
    print(f"Found {sk} Record: {existing_data}")

    return LeagueData.from_dynamodb(existing_data)
