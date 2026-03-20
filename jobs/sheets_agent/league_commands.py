import json

import requests

import constants
import sheets_helper
from sheets_helper import SheetNotSetupError
from aws_services import AWSServices

_SHEET_NOT_SHARED_MSG = (
    "📋 The bot cannot access this league's Google Sheet. "
    f"Make sure it has been shared (with Editor access) to: `{constants.GOOGLE_SERVICE_ACCOUNT_EMAIL}`\n"
    "If you already shared it, verify the email above matches what you used — then try again."
)

_SERVER_CONFIG_MISSING = "🙀 This server is not set up! Run `/setup-server` first to get started."
_LEAGUE_MISSING = "🙀 No league found! Use `/league-list` to see existing leagues."
_REQUIRE_ORGANIZER_ROLE = "🙅‍♀️ Sorry! Only users with this server's organizer role are authorized to request this action."

_SERVER_PK_PREFIX = "SERVER#"
_LEAGUE_SK_PREFIX = "LEAGUE#"
_CONFIG_SK = "CONFIG"

_DISCORD_API_BASE = "https://discord.com/api/v10"
_BOT_AUTH_HEADERS = {
    "Authorization": f"Bot {constants.DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}


def _get_server_config(server_id: str, table) -> dict | None:
    response = table.get_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": _CONFIG_SK})
    return response.get("Item")


def _get_league_data(server_id: str, league_id: str, table) -> dict | None:
    response = table.get_item(Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"})
    return response.get("Item")


def _verify_organizer(event_body: dict, table) -> str | None:
    """Returns an error string if the user is not an organizer, otherwise None."""
    server_id = event_body["guild_id"]
    config = _get_server_config(server_id, table)
    if not config:
        return _SERVER_CONFIG_MISSING
    organizer_role = config.get("organizer_role")
    user_roles = event_body.get("member", {}).get("roles", [])
    if organizer_role not in user_roles:
        return _REQUIRE_ORGANIZER_ROLE
    return None


def _get_command_input(event_body: dict, name: str) -> str | None:
    options = event_body.get("data", {}).get("options", [])
    option = next((o for o in options if o["name"] == name), None)
    return option["value"] if option else None


def _add_discord_role(guild_id: str, user_id: str, role_id: str) -> bool:
    url = f"{_DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    print(f"[discord] PUT {url}")
    response = requests.put(url, headers=_BOT_AUTH_HEADERS)
    print(f"[discord] Response status: {response.status_code}")
    return response.status_code == 204


def _enqueue_remove_roles(server_id: str, user_ids: list, role_id: str, sqs_queue) -> None:
    batch = []
    for idx, uid in enumerate(user_ids):
        batch.append({
            "Id": str(idx),
            "MessageBody": json.dumps({"guild_id": server_id, "user_id": uid, "role_id": role_id}),
        })
        if len(batch) == 10:
            sqs_queue.send_messages(Entries=batch)
            batch = []
    if batch:
        sqs_queue.send_messages(Entries=batch)


def handle_league_setup(event_body: dict, aws_services: AWSServices) -> str:
    error = _verify_organizer(event_body, aws_services.dynamodb_table)
    if error:
        return error

    server_id = event_body["guild_id"]
    league_id = _get_command_input(event_body, "league_name")

    league_data = _get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return _LEAGUE_MISSING

    try:
        sheets_helper.setup_league_participants_sheet(spreadsheet_url=league_data["google_sheets_link"])
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-setup: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    return f"✅ Participants sheet set up for **{league_data['league_name']}** (`{league_id}`)!"


def handle_league_join(event_body: dict, aws_services: AWSServices) -> str:
    server_id = event_body["guild_id"]
    league_id = _get_command_input(event_body, "league_name")

    league_data = _get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return _LEAGUE_MISSING

    if not league_data.get("join_enabled", False):
        return f"❌ Joining is not currently enabled for league **{league_data['league_name']}** (`{league_id}`)."

    discord_id = event_body["member"]["user"]["id"]
    member = event_body.get("member", {})
    participant_name = (
        member.get("nick")
        or member.get("user", {}).get("global_name")
        or member.get("user", {}).get("username")
    )

    try:
        sheets_helper.append_league_participant(
            spreadsheet_url=league_data["google_sheets_link"],
            discord_id=discord_id,
            participant_name=participant_name,
        )
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except SheetNotSetupError:
        return (
            f"⚠️ The Participants sheet hasn't been set up for **{league_data['league_name']}** yet. "
            "An organizer needs to run `/league-setup` first."
        )
    except ValueError:
        return "❌ This league's Google Sheets link is invalid. An organizer needs to update it with `/league-update`."
    except RuntimeError as e:
        print(f"[sheets_agent] league-join: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    return f"✅ You've been added to **{league_data['league_name']}** (`{league_id}`) as **{participant_name}**!"


def handle_league_sync_participants(event_body: dict, aws_services: AWSServices) -> str:
    error = _verify_organizer(event_body, aws_services.dynamodb_table)
    if error:
        return error

    server_id = event_body["guild_id"]
    league_id = _get_command_input(event_body, "league_name")

    league_data = _get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return _LEAGUE_MISSING

    try:
        current_active = sheets_helper.get_active_participants(league_data["google_sheets_link"])
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-sync-participants: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    old_player_ids = set(league_data.get("active_players", {}).keys())
    new_player_ids = set(current_active.keys())
    added_ids = new_player_ids - old_player_ids
    removed_ids = old_player_ids - new_player_ids

    active_participant_role = league_data.get("active_participant_role")
    if active_participant_role:
        for user_id in added_ids:
            _add_discord_role(guild_id=server_id, user_id=user_id, role_id=active_participant_role)
        if removed_ids:
            _enqueue_remove_roles(
                server_id=server_id,
                user_ids=list(removed_ids),
                role_id=active_participant_role,
                sqs_queue=aws_services.remove_role_sqs_queue,
            )

    aws_services.dynamodb_table.update_item(
        Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"},
        UpdateExpression="SET active_players = :active_players",
        ExpressionAttributeValues={":active_players": current_active},
    )

    lines = [f"✅ Synced active participants for **{league_data['league_name']}** (`{league_id}`):"]
    lines.append(f"• Total active: {len(new_player_ids)}")
    if added_ids:
        lines.append(f"• Added: {len(added_ids)}")
    if removed_ids:
        lines.append(f"• Removed: {len(removed_ids)}")
    if not added_ids and not removed_ids:
        lines.append("• No changes")
    if active_participant_role:
        if added_ids:
            lines.append(f"• Role assigned to {len(added_ids)} new player(s)")
        if removed_ids:
            lines.append(f"• Role removal queued for {len(removed_ids)} player(s)")
    else:
        lines.append("• ℹ️ No active participant role configured — roles were not assigned/removed")

    return "\n".join(lines)
