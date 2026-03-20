import constants
import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
import utils.google_sheets_helper as sheets_helper
from utils.google_sheets_helper import SheetNotSetupError
import utils.discord_api_helper as discord_helper
import utils.queue_role_removal as role_removal_queue
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.league_data import LeagueData

_SHEET_NOT_SHARED_MSG = (
    "📋 The bot cannot access this league's Google Sheet. "
    f"Make sure it has been shared (with Editor access) to: `{constants.GOOGLE_SERVICE_ACCOUNT_EMAIL}`\n"
    "If you already shared it, verify the email above matches what you used — then try again."
)


def handle_league_setup(event: DiscordEvent, aws_services: AWSServices) -> str:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message.content

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data.content

    try:
        sheets_helper.setup_league_participants_sheet(spreadsheet_url=league_data.google_sheets_link)
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-setup: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    return f"✅ Participants sheet set up for **{league_data.league_name}** (`{league_id}`)!"


def handle_league_join(event: DiscordEvent, aws_services: AWSServices) -> str:
    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data.content

    if not league_data.join_enabled:
        return f"❌ Joining is not currently enabled for league **{league_data.league_name}** (`{league_id}`)."

    discord_id = event.get_user_id()
    participant_name = event.get_display_name()

    try:
        sheets_helper.append_league_participant(
            spreadsheet_url=league_data.google_sheets_link,
            discord_id=discord_id,
            participant_name=participant_name,
        )
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except SheetNotSetupError:
        return (
            f"⚠️ The Participants sheet hasn't been set up for **{league_data.league_name}** yet. "
            "An organizer needs to run `/league-setup` first."
        )
    except ValueError:
        return "❌ This league's Google Sheets link is invalid. An organizer needs to update it with `/league-update`."
    except RuntimeError as e:
        print(f"[sheets_agent] league-join: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    return f"✅ You've been added to **{league_data.league_name}** (`{league_id}`) as **{participant_name}**!"


def handle_league_sync_participants(event: DiscordEvent, aws_services: AWSServices) -> str:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message.content

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data.content

    try:
        current_active = sheets_helper.get_active_participants(league_data.google_sheets_link)
    except PermissionError:
        return _SHEET_NOT_SHARED_MSG
    except RuntimeError as e:
        print(f"[sheets_agent] league-sync-participants: RuntimeError: {e}")
        return "❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator."

    old_player_ids = set(league_data.active_players.keys())
    new_player_ids = set(current_active.keys())
    added_ids = new_player_ids - old_player_ids
    removed_ids = old_player_ids - new_player_ids

    if league_data.active_participant_role:
        for user_id in added_ids:
            discord_helper.add_role_to_user(
                guild_id=server_id,
                user_id=user_id,
                role_id=league_data.active_participant_role,
            )
        if removed_ids:
            role_removal_queue.enqueue_remove_role_jobs(
                server_id=server_id,
                user_ids=list(removed_ids),
                role_id=league_data.active_participant_role,
                sqs_queue=aws_services.remove_role_sqs_queue,
            )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id},
        UpdateExpression=f"SET {LeagueData.Keys.ACTIVE_PLAYERS} = :active_players",
        ExpressionAttributeValues={":active_players": current_active},
    )

    lines = [f"✅ Synced active participants for **{league_data.league_name}** (`{league_id}`):"]
    lines.append(f"• Total active: {len(new_player_ids)}")
    if added_ids:
        lines.append(f"• Added: {len(added_ids)}")
    if removed_ids:
        lines.append(f"• Removed: {len(removed_ids)}")
    if not added_ids and not removed_ids:
        lines.append("• No changes")
    if league_data.active_participant_role:
        if added_ids:
            lines.append(f"• Role assigned to {len(added_ids)} new player(s)")
        if removed_ids:
            lines.append(f"• Role removal queued for {len(removed_ids)} player(s)")
    else:
        lines.append("• ℹ️ No active participant role configured — roles were not assigned/removed")

    return "\n".join(lines)
