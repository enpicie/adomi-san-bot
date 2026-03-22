_SERVER_PK_PREFIX = "SERVER#"
_LEAGUE_SK_PREFIX = "LEAGUE#"
_CONFIG_SK = "CONFIG"

SERVER_CONFIG_MISSING = "🙀 This server is not set up! Run `/setup-server` first to get started."
LEAGUE_MISSING = "🙀 No league found! Use `/league-list` to see existing leagues."
REQUIRE_ORGANIZER_ROLE = "🙅‍♀️ Sorry! Only users with this server's organizer role are authorized to request this action."


def get_server_config(server_id: str, table) -> dict | None:
    response = table.get_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": _CONFIG_SK})
    return response.get("Item")


def get_league_data(server_id: str, league_id: str, table) -> dict | None:
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
    options = event_body.get("data", {}).get("options", [])
    option = next((o for o in options if o["name"] == name), None)
    return option["value"] if option else None


def league_key(server_id: str, league_id: str) -> dict:
    return {"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"}
