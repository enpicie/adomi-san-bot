import json
import time

import requests

import constants
import sheets_helper
from sheets_helper import SheetNotSetupError
from aws_services import AWSServices
from participants_sheet import STATUS_ACTIVE, STATUS_QUEUED, STATUS_INACTIVE, STATUS_DNF

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


def _discord_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a Discord API request with automatic 429 retry."""
    response = requests.request(method, url, headers=_BOT_AUTH_HEADERS, timeout=10, **kwargs)
    if response.status_code == 429:
        retry_after = response.json().get("retry_after", 1.0)
        print(f"[discord] rate limited on {method} {url}, sleeping {retry_after}s")
        time.sleep(retry_after)
        response = requests.request(method, url, headers=_BOT_AUTH_HEADERS, timeout=10, **kwargs)
    return response


def _add_discord_role(guild_id: str, user_id: str, role_id: str) -> bool:
    url = f"{_DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    print(f"[discord] PUT {url}")
    response = _discord_request("PUT", url)
    print(f"[discord] Response status: {response.status_code}")
    return response.status_code == 204


def _search_discord_member(guild_id: str, username: str) -> str | None:
    """Look up a Discord snowflake by exact username handle via guild member search."""
    url = f"{_DISCORD_API_BASE}/guilds/{guild_id}/members/search"
    response = _discord_request("GET", url, params={"query": username, "limit": 10})
    if response.status_code != 200:
        print(f"[discord] member search failed for {username!r}: status={response.status_code}")
        return None
    for member in response.json():
        if member.get("user", {}).get("username") == username:
            return member["user"]["id"]
    return None


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
        already_existed = sheets_helper.setup_league_participants_sheet(spreadsheet_url=league_data["google_sheets_link"])
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-setup: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    league_name = league_data["league_name"]
    if already_existed:
        return f"✅ Styling has been applied to the existing Participants sheet for **{league_name}** (`{league_id}`)."
    return f"✅ Participants sheet created and set up for **{league_name}** (`{league_id}`)!"


def _send_channel_message(channel_id: str, content: str) -> None:
    url = f"{_DISCORD_API_BASE}/channels/{channel_id}/messages"
    response = requests.post(url, headers=_BOT_AUTH_HEADERS, json={"content": content})
    print(f"[discord] POST {url} status={response.status_code}")


def handle_league_join(event_body: dict, aws_services: AWSServices) -> str:
    server_id = event_body["guild_id"]
    league_id = _get_command_input(event_body, "league_name")

    league_data = _get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return _LEAGUE_MISSING

    if not league_data.get("join_enabled", False):
        return f"❌ Joining is not currently enabled for league **{league_data['league_name']}** (`{league_id}`)."

    # Username = user's "@" handle (sheet key); snowflake = actual Discord user ID for API calls
    # nick = server display name; global_name = user's global display name
    member = event_body.get("member", {})
    user = member.get("user", {})
    discord_id = user.get("username")
    snowflake = user.get("id")
    participant_name = (
        member.get("nick")
        or user.get("global_name")
        or user.get("username")
    )
    league_name = league_data["league_name"]
    sheets_url = league_data["google_sheets_link"]

    try:
        row_number, current_status = sheets_helper.find_participant(
            spreadsheet_url=sheets_url,
            discord_id=discord_id,
        )

        if current_status == STATUS_DNF:
            return f"❌ You are marked as **DNF** in **{league_name}** (`{league_id}`). Contact an organizer to change your status."

        if current_status == STATUS_ACTIVE:
            return f"✅ You're already listed as an **ACTIVE** participant in **{league_name}** (`{league_id}`)!"

        if current_status == STATUS_QUEUED:
            return f"✅ You're already **QUEUED** for **{league_name}** (`{league_id}`)!"

        if current_status == STATUS_INACTIVE:
            sheets_helper.update_participant_status(sheets_url, row_number, STATUS_QUEUED)
            reply = f"✅ Your status in **{league_name}** (`{league_id}`) has been changed from **INACTIVE** to **QUEUED**!"
        else:
            sheets_helper.append_league_participant(
                spreadsheet_url=sheets_url,
                discord_id=discord_id,
                participant_name=participant_name,
            )
            reply = f"✅ You've been added to **{league_name}** (`{league_id}`) as **{participant_name}**!"

    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except SheetNotSetupError:
        return (
            f"⚠️ The Participants sheet hasn't been set up for **{league_name}** yet. "
            "An organizer needs to run `/league-setup` first."
        )
    except ValueError:
        return "❌ This league's Google Sheets link is invalid. An organizer needs to update it with `/league-update`."
    except RuntimeError as e:
        print(f"[sheets_agent] league-join: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    # Cache participant data so sync can assign Discord roles before their sheet status becomes ACTIVE
    if snowflake:
        queued_entry = {"discord_id": snowflake, "display_name": participant_name}
        aws_services.dynamodb_table.update_item(
            Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"},
            UpdateExpression="SET queued_participants = if_not_exists(queued_participants, :empty), queued_participants.#u = :entry",
            ExpressionAttributeNames={"#u": discord_id},
            ExpressionAttributeValues={":empty": {}, ":entry": queued_entry},
        )

    config = _get_server_config(server_id, aws_services.dynamodb_table)
    notification_channel_id = config.get("notification_channel_id") if config else None
    if notification_channel_id:
        action = "re-queued" if current_status == STATUS_INACTIVE else "joined"
        _send_channel_message(
            notification_channel_id,
            f"📋 **{participant_name}** (`@{discord_id}`) has {action} **{league_name}** (`{league_id}`).",
        )

    return reply


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

    old_active_players = league_data.get("active_players", {})
    queued_participants = league_data.get("queued_participants", {})

    # Phase 1: resolve snowflakes from cached state (retained active players + queued_participants)
    resolved_snowflakes = {}  # handle -> snowflake
    needs_api_lookup = []
    for handle in current_active:
        old_player = old_active_players.get(handle, {})
        snowflake = old_player.get("discord_id") if isinstance(old_player, dict) else None
        if not snowflake:
            snowflake = queued_participants.get(handle, {}).get("discord_id")
        if snowflake:
            resolved_snowflakes[handle] = snowflake
        else:
            needs_api_lookup.append(handle)

    # Phase 2: API lookup for handles with no cached snowflake (manually added to sheet)
    api_unresolved = []
    for handle in needs_api_lookup:
        snowflake = _search_discord_member(server_id, handle)
        if snowflake:
            resolved_snowflakes[handle] = snowflake
            print(f"[sync] resolved snowflake via API for handle={handle!r}")
        else:
            api_unresolved.append(handle)
            print(f"[sync] could not resolve snowflake for handle={handle!r}")
        time.sleep(0.5)

    # Build enriched active_players: {handle -> {"discord_id": snowflake, "display_name": name}}
    new_active_players = {
        handle: {
            "discord_id": resolved_snowflakes.get(handle),
            "display_name": display_name,
        }
        for handle, display_name in current_active.items()
    }

    old_handles = set(old_active_players.keys())
    new_handles = set(new_active_players.keys())
    added_handles = new_handles - old_handles
    removed_handles = old_handles - new_handles

    active_participant_role = league_data.get("active_participant_role")
    remove_snowflakes = []

    if active_participant_role:
        for handle in added_handles:
            snowflake = new_active_players[handle]["discord_id"]
            if snowflake:
                _add_discord_role(guild_id=server_id, user_id=snowflake, role_id=active_participant_role)
                time.sleep(0.5)
            else:
                print(f"[sync] skipping role assignment for handle={handle!r}: no snowflake")

        for handle in removed_handles:
            old_player = old_active_players.get(handle, {})
            snowflake = old_player.get("discord_id") if isinstance(old_player, dict) else None
            if snowflake:
                remove_snowflakes.append(snowflake)
            else:
                print(f"[sync] skipping role removal for handle={handle!r}: no snowflake")

        if remove_snowflakes:
            _enqueue_remove_roles(
                server_id=server_id,
                user_ids=remove_snowflakes,
                role_id=active_participant_role,
                sqs_queue=aws_services.remove_role_sqs_queue,
            )

    aws_services.dynamodb_table.update_item(
        Key={"PK": f"{_SERVER_PK_PREFIX}{server_id}", "SK": f"{_LEAGUE_SK_PREFIX}{league_id}"},
        UpdateExpression="SET active_players = :active_players",
        ExpressionAttributeValues={":active_players": new_active_players},
    )

    lines = [f"✅ Synced active participants for **{league_data['league_name']}** (`{league_id}`):"]
    lines.append(f"• Total active: {len(new_handles)}")
    if added_handles:
        lines.append(f"• Added: {len(added_handles)}")
    if removed_handles:
        lines.append(f"• Removed: {len(removed_handles)}")
    if not added_handles and not removed_handles:
        lines.append("• No changes")
    if active_participant_role:
        assigned = sum(1 for h in added_handles if new_active_players[h]["discord_id"])
        if assigned:
            lines.append(f"• Role assigned to {assigned} new player(s)")
        if remove_snowflakes:
            lines.append(f"• Role removal queued for {len(remove_snowflakes)} player(s)")
        if api_unresolved:
            lines.append(
                f"• ⚠️ {len(api_unresolved)} player(s) could not be found in this server — "
                f"role not assigned: {', '.join(f'`{h}`' for h in api_unresolved)}"
            )
    else:
        lines.append("• ℹ️ No active participant role configured — roles were not assigned/removed")

    return "\n".join(lines)


def handle_league_deactivate(event_body: dict, aws_services: AWSServices) -> str:
    server_id = event_body["guild_id"]
    league_id = _get_command_input(event_body, "league_name")

    league_data = _get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return _LEAGUE_MISSING

    # Resolve target: organizer may specify another player via the user option
    player_snowflake = _get_command_input(event_body, "player")
    if player_snowflake:
        resolved_users = event_body.get("data", {}).get("resolved", {}).get("users", {})
        target_discord_id = resolved_users.get(player_snowflake, {}).get("username")
        if not target_discord_id:
            return "❌ Could not resolve the specified player."
    else:
        member = event_body.get("member", {})
        target_discord_id = member.get("user", {}).get("username")

    dnf = _get_command_input(event_body, "dnf")
    new_status = STATUS_DNF if dnf else STATUS_INACTIVE
    status_label = "DNF" if new_status == STATUS_DNF else "INACTIVE"
    league_name = league_data["league_name"]

    try:
        row_number, current_status = sheets_helper.find_participant(
            spreadsheet_url=league_data["google_sheets_link"],
            discord_id=target_discord_id,
        )
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-deactivate: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    if row_number is None:
        if player_snowflake:
            return f"❌ **{target_discord_id}** is not listed in the Participants sheet for **{league_name}**."
        return f"❌ You are not listed in the Participants sheet for **{league_name}**."

    if current_status == new_status:
        if player_snowflake:
            return f"ℹ️ **{target_discord_id}** is already marked as **{status_label}** in **{league_name}**."
        return f"ℹ️ You are already marked as **{status_label}** in **{league_name}**."

    try:
        sheets_helper.update_participant_status(league_data["google_sheets_link"], row_number, new_status)
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-deactivate: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    if player_snowflake:
        return f"✅ **{target_discord_id}** has been marked as **{status_label}** in **{league_name}** (`{league_id}`)."
    return f"✅ You have been marked as **{status_label}** in **{league_name}** (`{league_id}`)."
