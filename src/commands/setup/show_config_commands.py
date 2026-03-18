from datetime import datetime, timezone

import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def event_view(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    reg_state = "🟢 Open" if event_data_result.register_enabled else "🔴 Closed"
    reg_count = len(event_data_result.registered or {})

    checkin_state = "🟢 Open" if event_data_result.check_in_enabled else "🔴 Closed"
    checkin_count = len(event_data_result.checked_in or {})

    participant_role = (
        message_helper.get_role_ping(event_data_result.participant_role)
        if event_data_result.participant_role
        else "Not set"
    )

    def _discord_timestamp(iso_str):
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        return f"<t:{int(dt.timestamp())}:f>"

    start_str = _discord_timestamp(event_data_result.start_time) if event_data_result.start_time else "Not set"
    end_str = _discord_timestamp(event_data_result.end_time) if event_data_result.end_time else "Not set"

    lines = [
        f"**Event: {event_data_result.event_name or event_id}**",
        f"**Start:** {start_str}",
        f"**End:** {end_str}",
        f"**Registration:** {reg_state} | {reg_count} registered",
        f"**Check-in:** {checkin_state} | {checkin_count} checked in",
        f"**Participant Role:** {participant_role}",
    ]

    if event_data_result.start_message:
        lines.append(f"**Start Message:** {event_data_result.start_message}")
    if event_data_result.end_message:
        lines.append(f"**End Message:** {event_data_result.end_message}")
    if event_data_result.startgg_url:
        lines.append(f"**start.gg:** {event_data_result.startgg_url}")

    return ResponseMessage(content="\n".join(lines)).with_silent_pings()


def show_event_roles(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()

    config_result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(config_result, ResponseMessage):
        return config_result

    event_id = event.get_command_input_value("event_name")
    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    participant_role = (
        message_helper.get_role_ping(event_data_result.participant_role)
        if event_data_result.participant_role
        else "No Participant role set"
    )

    return ResponseMessage(
        content=f"**Event Roles:**\n"
                f"- Organizer: {message_helper.get_role_ping(config_result.organizer_role)}\n"
                f"- Participant: {participant_role}"
    ).with_silent_pings()
