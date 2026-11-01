from boto3.dynamodb.conditions import Key

_SERVER_PK_PREFIX = "SERVER#"
_LEAGUE_SK_PREFIX = "LEAGUE#"
_CONFIG_SK = "CONFIG"
_EVENT_SK_PREFIX = "EVENT#"
_PLAN_SK_PREFIX = "SCHEDULE_PLAN#"

SERVER_CONFIG_MISSING = "🙀 This server is not set up! Run `/setup-server` first to get started."
LEAGUE_MISSING = "🙀 No league found! Use `/league-list` to see existing leagues."
REQUIRE_ORGANIZER_ROLE = "🙅‍♀️ Sorry! Only users with this server's organizer role are authorized to request this action."


def get_server_config(server_id: str, table) -> dict | None:
    """Get the server CONFIG record. Returns item dict or None."""
    response = table.get_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": _CONFIG_SK})
    return response.get("Item")


def get_league_data(server_id: str, league_id: str, table) -> dict | None:
    """Get a league's LEAGUE record for a server. Returns item dict or None."""
    response = table.get_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"})
    return response.get("Item")


def verify_organizer(event_body: dict, table) -> str | None:
    """Returns an error string if the user is not an organizer, otherwise None."""
    server_id = event_body["guild_id"]
    config = get_server_config(server_id, table)
    if not config:
        return SERVER_CONFIG_MISSING
    organizer_role = config.get("organizer_role")
    user_roles = event_body.get("member", {}).get("roles", [])
    if organizer_role not in user_roles:
        return REQUIRE_ORGANIZER_ROLE
    return None


def get_command_input(event_body: dict, name: str) -> str | None:
    """Return the value of a named slash-command option from the interaction body, or None."""
    options = event_body.get("data", {}).get("options", [])
    option = next((o for o in options if o["name"] == name), None)
    return option["value"] if option else None


def league_key(server_id: str, league_id: str) -> dict:
    """Build the DynamoDB primary key dict for a league record."""
    return {"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"}


# ── Events / schedule ───────────────────────────────────────────────────────
# MIRROR: src/database/dynamodb_utils.py — keep in sync.

def event_key(server_id: str, event_id: str) -> dict:
    """Build the DynamoDB primary key dict for an EVENT record."""
    return {"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_EVENT_SK_PREFIX}{event_id}"}


def get_full_events_for_server(server_id: str, table) -> list:
    """Query all EVENT records for a server by PK + SK prefix. Returns item dicts."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"{_SERVER_PK_PREFIX}{server_id}")
        & Key("SK").begins_with(_EVENT_SK_PREFIX)
    )
    return response.get("Items", [])


def get_schedule_plans_for_server(server_id: str, table) -> list:
    """Query all SCHEDULE_PLAN records for a server. Returns item dicts."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"{_SERVER_PK_PREFIX}{server_id}")
        & Key("SK").begins_with(_PLAN_SK_PREFIX)
    )
    return response.get("Items", [])


def delete_schedule_plan(server_id: str, plan_name: str, table) -> None:
    """Delete a SCHEDULE_PLAN record by plan name (normalized for the key).

    MIRROR: src/database/dynamodb_utils.py delete_schedule_plan — plans are keyed
    on SchedulePlan.normalize_name(plan_name), while `plan_name` on the item keeps
    the display name, so the display name must be normalized to hit the key.
    """
    sk = _PLAN_SK_PREFIX + (plan_name or "").strip().lower()
    table.delete_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": sk})
