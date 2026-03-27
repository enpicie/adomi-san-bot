import json

import constants
import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.league_data import LeagueData

LEAGUE_ID_MAX_LENGTH = 4


def _dispatch_to_sheets_agent(command_name: str, event: DiscordEvent, aws_services: AWSServices) -> None:
    payload = json.dumps({"command_name": command_name, "event_body": event.event_body})
    aws_services.sheets_agent_sqs_queue.send_message(MessageBody=payload)
    print(f"[league_commands] dispatched {command_name!r} to sheets_agent")


def _parse_role_id(role_input: str) -> str:
    """Strip Discord mention format (<@&id>) if present, returning just the numeric snowflake."""
    if role_input and role_input.startswith("<@&") and role_input.endswith(">"):
        return role_input[3:-1]
    return role_input


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
    active_participant_role = _parse_role_id(event.get_command_input_value("active_participant_role") or "")

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
        LeagueData.Keys.REPORT_ENABLED: False,
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
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    new_name = event.get_command_input_value("new_name")
    new_link = event.get_command_input_value("google_sheets_link")
    new_role = _parse_role_id(event.get_command_input_value("active_participant_role") or "")

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
    role_display = message_helper.get_role_ping(league_data.active_participant_role) if league_data.active_participant_role else "not set"
    return ResponseMessage(
        content=(
            f"📋 **{league_data.league_name}** (`{league_data.league_id}`)\n"
            f"• Google Sheet: {league_data.google_sheets_link}\n"
            f"• Active Players: {player_count}\n"
            f"• Join Enabled: {'✅' if league_data.join_enabled else '❌'}\n"
            f"• Report Enabled: {'✅' if league_data.report_enabled else '❌'}\n"
            f"• Active Participant Role: {role_display}"
        )
    ).with_silent_pings()


def setup_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    _dispatch_to_sheets_agent("league-setup", event, aws_services)
    return ResponseMessage(content="⏳ Setting up the Participants sheet...")


def join_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    _dispatch_to_sheets_agent("league-join", event, aws_services)
    return ResponseMessage(content="⏳ Adding you to the league...")


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
    _dispatch_to_sheets_agent("league-sync-participants", event, aws_services)
    return ResponseMessage(content="⏳ Syncing participants from the sheet... This may take a few minutes.")


def report_score(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    if not league_data.report_enabled:
        return ResponseMessage(content="❌ Score reporting is currently closed for this league.")

    _dispatch_to_sheets_agent("league-report-score", event, aws_services)
    return ResponseMessage(content="⏳ Reporting score...")


def toggle_report_score(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    league_id = event.get_command_input_value("league_name")  # autocomplete value = league_id

    league_data = db_helper.get_server_league_data_or_fail(server_id, league_id, aws_services.dynamodb_table)
    if isinstance(league_data, ResponseMessage):
        return league_data

    report_state = event.get_command_input_value("state")
    should_enable = report_state == "Start"
    print(f"{LeagueData.Keys.REPORT_ENABLED}: {should_enable} via input {report_state}")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": LeagueData.Keys.SK_LEAGUE_PREFIX + league_id},
        UpdateExpression=f"SET {LeagueData.Keys.REPORT_ENABLED} = :report_enabled",
        ExpressionAttributeValues={":report_enabled": should_enable}
    )

    content = (
        f"🟢 Score reporting started! Participants can now report scores for **{league_data.league_name}** with `/league-report-score`"
        if should_enable
        else f"🔴 Score reporting closed! **{league_data.league_name}** will no longer accept score reports."
    )
    return ResponseMessage(content=content)


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


def deactivate_league_participant(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    if event.get_command_input_value("player"):
        error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
        if error_message:
            return ResponseMessage(content="🙅‍♀️ Only organizers can deactivate other players. To deactivate yourself, call `/league-deactivate` without the `player` parameter.")
    _dispatch_to_sheets_agent("league-deactivate", event, aws_services)
    return ResponseMessage(content="⏳ Updating your participant status...")
