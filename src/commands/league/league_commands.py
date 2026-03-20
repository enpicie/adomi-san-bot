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

LEAGUE_ID_MAX_LENGTH = 4

_SHEET_NOT_SHARED_MSG = (
    "📋 The bot cannot access this league's Google Sheet. "
    f"Make sure it has been shared (with Editor access) to: `{constants.GOOGLE_SERVICE_ACCOUNT_EMAIL}`\n"
    "If you already shared it, verify the email above matches what you used — then try again."
)


def _validate_league_id(league_id: str) -> str | None:
    """Returns an error message string if invalid, otherwise None."""
    if len(league_id) > LEAGUE_ID_MAX_LENGTH:
        return f"❌ League ID must be {LEAGUE_ID_MAX_LENGTH} characters or fewer."
    return None


def create_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_id").upper()
    league_name = event.get_command_input_value("league_name")
    google_sheets_link = event.get_command_input_value("google_sheets_link")
    active_participant_role = event.get_command_input_value("active_participant_role")

    validation_error = _validate_league_id(league_id)
    if validation_error:
        return ResponseMessage(content=validation_error)

    existing = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(existing, LeagueData):
        return ResponseMessage(content=f"❌ A league with ID `{league_id}` already exists. Choose a different ID.")

    item = {
        "PK": db_helper.build_server_pk(server_id),
        "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id,
        LeagueData.Keys.SERVER_ID: server_id,
        LeagueData.Keys.LEAGUE_ID: league_id,
        LeagueData.Keys.LEAGUE_NAME: league_name,
        LeagueData.Keys.GOOGLE_SHEETS_LINK: google_sheets_link,
        LeagueData.Keys.ACTIVE_PLAYERS: {},
        LeagueData.Keys.JOIN_ENABLED: False,
    }
    if active_participant_role:
        item[LeagueData.Keys.ACTIVE_PARTICIPANT_ROLE] = active_participant_role
    aws_services.dynamodb_table.put_item(Item=item)

    return ResponseMessage(
        content=(
            f"✅ League **{league_name}** (`{league_id}`) created!\n"
            f"📊 To connect your Google Sheet, please share it with the bot's service account:\n"
            f"`{constants.GOOGLE_SERVICE_ACCOUNT_EMAIL}`\n"
            f"Then run `/league-setup` to initialize the Participants sheet."
        )
    )


def update_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_id").upper()

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    new_name = event.get_command_input_value("league_name")
    new_link = event.get_command_input_value("google_sheets_link")
    new_role = event.get_command_input_value("active_participant_role")

    if not new_name and not new_link and not new_role:
        return ResponseMessage(content="ℹ️ No changes provided.")

    update_expressions = []
    expression_values = {}

    if new_name:
        update_expressions.append(f"{LeagueData.Keys.LEAGUE_NAME} = :league_name")
        expression_values[":league_name"] = new_name
    if new_link:
        update_expressions.append(f"{LeagueData.Keys.GOOGLE_SHEETS_LINK} = :google_sheets_link")
        expression_values[":google_sheets_link"] = new_link
    if new_role:
        update_expressions.append(f"{LeagueData.Keys.ACTIVE_PARTICIPANT_ROLE} = :active_participant_role")
        expression_values[":active_participant_role"] = new_role

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id},
        UpdateExpression="SET " + ", ".join(update_expressions),
        ExpressionAttributeValues=expression_values
    )

    changes = []
    if new_name:
        changes.append(f"📝 Name: `{league_data.league_name}` → `{new_name}`")
    if new_link:
        changes.append(f"📊 Google Sheets link updated")
    if new_role:
        changes.append(f"🎭 Active participant role updated")

    change_summary = "\n".join(f"• {c}" for c in changes)
    return ResponseMessage(content=f"✅ League `{league_id}` updated:\n{change_summary}")


def list_leagues(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    leagues = db_helper.get_leagues_for_server(server_id, aws_services.dynamodb_table)

    if not leagues:
        return ResponseMessage(content="ℹ️ No leagues found for this server.")

    lines = [f"• **{name}** (`{lid}`)" for name, lid in leagues]
    return ResponseMessage(content="📋 **Leagues:**\n" + "\n".join(lines))


def view_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    player_count = len(league_data.active_players)
    role_display = f"`{league_data.active_participant_role}`" if league_data.active_participant_role else "not set"
    return ResponseMessage(
        content=(
            f"📋 **{league_data.league_name}** (`{league_data.league_id}`)\n"
            f"• Google Sheet: {league_data.google_sheets_link}\n"
            f"• Active Players: {player_count}\n"
            f"• Join Enabled: {'✅' if league_data.join_enabled else '❌'}\n"
            f"• Active Participant Role: {role_display}"
        )
    )


def setup_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    try:
        sheets_helper.setup_league_participants_sheet(spreadsheet_url=league_data.google_sheets_link)
    except PermissionError:
        return ResponseMessage(content=_SHEET_NOT_SHARED_MSG)
    except RuntimeError as e:
        print(f"[league] setup_league: RuntimeError: {e}")
        return ResponseMessage(content="❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator.")

    return ResponseMessage(
        content=f"✅ Participants sheet set up for **{league_data.league_name}** (`{league_id}`)!"
    )


def join_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    if not league_data.join_enabled:
        return ResponseMessage(content=f"❌ Joining is not currently enabled for league **{league_data.league_name}** (`{league_id}`).")

    discord_id = event.get_user_id()
    participant_name = event.get_display_name()

    try:
        sheets_helper.append_league_participant(
            spreadsheet_url=league_data.google_sheets_link,
            discord_id=discord_id,
            participant_name=participant_name,
        )
    except PermissionError:
        return ResponseMessage(content=_SHEET_NOT_SHARED_MSG)
    except SheetNotSetupError:
        return ResponseMessage(
            content=f"⚠️ The Participants sheet hasn't been set up for **{league_data.league_name}** yet. "
                    f"An organizer needs to run `/league-setup` first."
        )
    except ValueError:
        return ResponseMessage(content="❌ This league's Google Sheets link is invalid. An organizer needs to update it with `/league-update`.")
    except RuntimeError as e:
        print(f"[league] join_league: RuntimeError: {e}")
        return ResponseMessage(content="❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator.")

    return ResponseMessage(
        content=f"✅ You've been added to **{league_data.league_name}** (`{league_id}`) as **{participant_name}**!"
    )


def toggle_join_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    join_state = event.get_command_input_value("state")
    should_enable = join_state == "Start"
    print(f"{LeagueData.Keys.JOIN_ENABLED}: {should_enable} via input {join_state}")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id},
        UpdateExpression=f"SET {LeagueData.Keys.JOIN_ENABLED} = :join_enabled",
        ExpressionAttributeValues={":join_enabled": should_enable}
    )

    content = (
        f"🟢 Joining started! Participants can begin joining **{league_data.league_name}** with `/league-join`"
        if should_enable
        else f"🔴 Joining closed! **{league_data.league_name}** will no longer accept new participants."
    )
    return ResponseMessage(content=content)


def sync_active_participants(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    try:
        current_active = sheets_helper.get_active_participants(league_data.google_sheets_link)
    except PermissionError:
        return ResponseMessage(content=_SHEET_NOT_SHARED_MSG)
    except RuntimeError as e:
        print(f"[league] sync_active_participants: RuntimeError: {e}")
        return ResponseMessage(content="❌ The bot's Google Sheets integration is misconfigured. Contact the bot administrator.")

    old_player_ids = set(league_data.active_players.keys())
    new_player_ids = set(current_active.keys())

    added_ids = new_player_ids - old_player_ids
    removed_ids = old_player_ids - new_player_ids

    if league_data.active_participant_role:
        for user_id in added_ids:
            discord_helper.add_role_to_user(
                guild_id=server_id,
                user_id=user_id,
                role_id=league_data.active_participant_role
            )
        if removed_ids:
            role_removal_queue.enqueue_remove_role_jobs(
                server_id=server_id,
                user_ids=list(removed_ids),
                role_id=league_data.active_participant_role,
                sqs_queue=aws_services.remove_role_sqs_queue
            )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id},
        UpdateExpression=f"SET {LeagueData.Keys.ACTIVE_PLAYERS} = :active_players",
        ExpressionAttributeValues={":active_players": current_active}
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

    return ResponseMessage(content="\n".join(lines))


def delete_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    aws_services.dynamodb_table.delete_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id}
    )

    return ResponseMessage(content=f"🗑️ League **{league_data.league_name}** (`{league_id}`) deleted.")
