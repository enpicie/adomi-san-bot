import time

import constants
import sheets_helper
from sheets_helper import SheetNotSetupError
from aws_services import AWSServices
import participants_sheet
import db_helper
import discord_api

_SHEET_NOT_SHARED_MSG = (
    "📋 The bot cannot access this league's Google Sheet. "
    f"Make sure it has been shared (with Editor access) to: `{constants.GOOGLE_SERVICE_ACCOUNT_EMAIL}`\n"
    "If you already shared it, verify the email above matches what you used — then try again."
)


def handle_league_setup(event_body: dict, aws_services: AWSServices) -> str:
    error = db_helper.verify_organizer(event_body, aws_services.dynamodb_table)
    if error:
        return error

    server_id = event_body["guild_id"]
    league_id = db_helper.get_command_input(event_body, "league_name")

    league_data = db_helper.get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return db_helper.LEAGUE_MISSING

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


def handle_league_join(event_body: dict, aws_services: AWSServices) -> str:
    server_id = event_body["guild_id"]
    league_id = db_helper.get_command_input(event_body, "league_name")

    league_data = db_helper.get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return db_helper.LEAGUE_MISSING

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

        if current_status == participants_sheet.STATUS_DNF:
            return f"❌ You are marked as **DNF** in **{league_name}** (`{league_id}`). Contact an organizer to change your status."

        if current_status == participants_sheet.STATUS_ACTIVE:
            return f"✅ You're already listed as an **ACTIVE** participant in **{league_name}** (`{league_id}`)!"

        if current_status == participants_sheet.STATUS_QUEUED:
            return f"✅ You're already **QUEUED** for **{league_name}** (`{league_id}`)!"

        if current_status == participants_sheet.STATUS_INACTIVE:
            sheets_helper.update_participant_status(sheets_url, row_number, participants_sheet.STATUS_QUEUED)
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
            Key=db_helper.league_key(server_id, league_id),
            UpdateExpression="SET queued_participants = if_not_exists(queued_participants, :empty), queued_participants.#u = :entry",
            ExpressionAttributeNames={"#u": discord_id},
            ExpressionAttributeValues={":empty": {}, ":entry": queued_entry},
        )

    config = db_helper.get_server_config(server_id, aws_services.dynamodb_table)
    notification_channel_id = config.get("notification_channel_id") if config else None
    if notification_channel_id:
        action = "re-queued" if current_status == participants_sheet.STATUS_INACTIVE else "joined"
        discord_api.send_channel_message(
            notification_channel_id,
            f"📋 **{participant_name}** (`@{discord_id}`) has {action} **{league_name}** (`{league_id}`).",
        )

    return reply


def handle_league_sync_participants(event_body: dict, aws_services: AWSServices) -> str:
    error = db_helper.verify_organizer(event_body, aws_services.dynamodb_table)
    if error:
        return error

    server_id = event_body["guild_id"]
    league_id = db_helper.get_command_input(event_body, "league_name")

    league_data = db_helper.get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return db_helper.LEAGUE_MISSING

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
        snowflake = discord_api.search_discord_member(server_id, handle)
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
    role_assigned_handles = []
    role_failed_handles = []

    if active_participant_role:
        for handle in added_handles:
            snowflake = new_active_players[handle]["discord_id"]
            if snowflake:
                success = discord_api.add_discord_role(guild_id=server_id, user_id=snowflake, role_id=active_participant_role)
                if success:
                    role_assigned_handles.append(handle)
                else:
                    role_failed_handles.append(handle)
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
            discord_api.enqueue_remove_roles(
                server_id=server_id,
                user_ids=remove_snowflakes,
                role_id=active_participant_role,
                sqs_queue=aws_services.remove_role_sqs_queue,
            )

    remaining_queued = {h: v for h, v in queued_participants.items() if h not in new_handles}
    aws_services.dynamodb_table.update_item(
        Key=db_helper.league_key(server_id, league_id),
        UpdateExpression="SET active_players = :active_players, queued_participants = :queued_participants",
        ExpressionAttributeValues={
            ":active_players": new_active_players,
            ":queued_participants": remaining_queued,
        },
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
        if role_assigned_handles:
            lines.append(f"• Role assigned to {len(role_assigned_handles)} new player(s)")
        if remove_snowflakes:
            lines.append(f"• Role removal queued for {len(remove_snowflakes)} player(s)")
        if role_failed_handles:
            lines.append(
                f"• ❌ Role assignment failed for {len(role_failed_handles)} player(s) — check bot permissions: "
                f"{', '.join(f'`{h}`' for h in role_failed_handles)}"
            )
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
    league_id = db_helper.get_command_input(event_body, "league_name")

    league_data = db_helper.get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return db_helper.LEAGUE_MISSING

    # Resolve target: organizer may specify another player via the user option
    player_snowflake = db_helper.get_command_input(event_body, "player")
    if player_snowflake:
        resolved_users = event_body.get("data", {}).get("resolved", {}).get("users", {})
        target_discord_id = resolved_users.get(player_snowflake, {}).get("username")
        if not target_discord_id:
            return "❌ Could not resolve the specified player."
    else:
        member = event_body.get("member", {})
        target_discord_id = member.get("user", {}).get("username")

    dnf = db_helper.get_command_input(event_body, "dnf")
    new_status = participants_sheet.STATUS_DNF if dnf else participants_sheet.STATUS_INACTIVE
    status_label = "DNF" if new_status == participants_sheet.STATUS_DNF else "INACTIVE"
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


def handle_league_report_score(event_body: dict, aws_services: AWSServices) -> str:
    server_id = event_body["guild_id"]
    league_id = db_helper.get_command_input(event_body, "league_name")

    league_data = db_helper.get_league_data(server_id, league_id, aws_services.dynamodb_table)
    if not league_data:
        return db_helper.LEAGUE_MISSING

    winner_snowflake = db_helper.get_command_input(event_body, "winner")
    loser_snowflake  = db_helper.get_command_input(event_body, "loser")
    score_str        = db_helper.get_command_input(event_body, "score")

    resolved_users = event_body.get("data", {}).get("resolved", {}).get("users", {})
    winner_id = resolved_users.get(winner_snowflake, {}).get("username")
    loser_id  = resolved_users.get(loser_snowflake,  {}).get("username")

    if not winner_id or not loser_id:
        return "❌ Could not resolve winner or loser."

    try:
        parts = (score_str or "").strip().split("-")
        if len(parts) != 2:
            raise ValueError()
        winner_score = int(parts[0])
        loser_score  = int(parts[1])
    except ValueError:
        return "❌ Invalid score format. Use `W-L` (e.g. `3-2`, winner score first)."

    sheets_url = league_data["google_sheets_link"]

    try:
        score_data = sheets_helper.get_score_report_data(sheets_url, winner_id, loser_id)
    except ValueError as e:
        return f"❌ {e}"
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-report-score: get_score_report_data error: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    try:
        prev_winner, prev_loser = sheets_helper.update_score_cells(sheets_url, score_data, winner_score, loser_score)
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-report-score: update_score_cells error: {e}")
        return "❌ Failed to update score cells. Contact the bot administrator."

    try:
        sheets_helper.append_report_log(
            sheets_url, league_id,
            score_data["tier"], score_data["group"],
            winner_id, loser_id, winner_score, loser_score,
        )
    except Exception as e:
        # Non-fatal — score was already written; log and continue
        print(f"[sheets_agent] league-report-score: append_report_log error: {e}")

    league_name = league_data["league_name"]
    lines = [f"✅ Score reported for **{league_name}** (`{league_id}`):"]
    lines.append(f"• **@{winner_id}** def. **@{loser_id}** `{winner_score}-{loser_score}`")
    lines.append(f"• Tier: {score_data['tier']} | Group: {score_data['group']}")

    if prev_winner or prev_loser:
        lines.append(
            f"• ⚠️ Previous score was `{prev_winner or '?'}-{prev_loser or '?'}` — overwritten"
        )

    return "\n".join(lines)
