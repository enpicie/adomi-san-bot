import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
import commands.event.startgg.startgg_api as startgg_api
from commands.event.event_helper import EventRecord, create_event_record, update_event_record, delete_event_record
from commands.event.timezone_helper import to_utc_iso
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData

def create_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    timezone = event.get_command_input_value("timezone")

    create_event_record(
        server_id=event.get_server_id(),
        record=EventRecord(
            name=event.get_command_input_value("event_name"),
            location=event.get_command_input_value("event_location"),
            start_time_utc=to_utc_iso(event.get_command_input_value("start_time"), timezone),
            end_time_utc=to_utc_iso(event.get_command_input_value("end_time"), timezone),
            description=event.get_command_input_value("event_description")
        ),
        table=aws_services.dynamodb_table
    )

    return ResponseMessage(content=f"Event '{event.get_command_input_value('event_name')}' created successfully.")


def update_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")
    timezone = event.get_command_input_value("timezone")
    new_name = event.get_command_input_value("new_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    update_event_record(
        server_id=server_id,
        event_id=event_id,
        record=EventRecord(
            name=new_name or event.get_command_input_value("event_name"),
            location=event.get_command_input_value("event_location"),
            start_time_utc=to_utc_iso(event.get_command_input_value("start_time"), timezone),
            end_time_utc=to_utc_iso(event.get_command_input_value("end_time"), timezone),
            description=event.get_command_input_value("event_description")
        ),
        table=aws_services.dynamodb_table
    )

    return ResponseMessage(content="Event updated successfully.")


def delete_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    # autocomplete value for event_name is the event_id
    event_id = event.get_command_input_value("event_name")

    delete_event_record(
        server_id=event.get_server_id(),
        event_id=event_id,
        table=aws_services.dynamodb_table
    )

    return ResponseMessage(content="Event deleted successfully.")


def create_event_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    event_url = event.get_command_input_value("event_link")
    if not startgg_api.is_valid_startgg_url(event_url):
        return ResponseMessage(
            content="😖 Sorry! This start.gg event link is not valid. "
                    "Make sure it is a link to an event in a tournament like this: "
                    "https://www.start.gg/tournament/midweek-melting/event/mbaacc-double-elim"
        )

    startgg_event = startgg_api.query_startgg_event(event_url)

    if not startgg_event.start_time_utc or not startgg_event.end_time_utc:
        return ResponseMessage(
            content="😔 Could not retrieve start/end times from this start.gg event. "
                    "Please create the event manually with `/event-create`."
        )

    server_id = event.get_server_id()
    event_id = create_event_record(
        server_id=server_id,
        record=EventRecord(
            name=startgg_event.event_name,
            location=startgg_event.location or "Online",
            start_time_utc=startgg_event.start_time_utc,
            end_time_utc=startgg_event.end_time_utc,
        ),
        table=aws_services.dynamodb_table
    )

    total_count = len(startgg_event.participants) + len(startgg_event.no_discord_participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]

    update_expressions = []
    expression_values = {":startgg_url": event_url}

    if startgg_event.participants:
        startgg_participants_data = {
            participant.user_id: participant.to_dict()
            for participant in startgg_event.participants
        }
        update_expressions.append(f"{EventData.Keys.REGISTERED} = :startgg_registered")
        expression_values[":startgg_registered"] = startgg_participants_data

    update_expressions.append(f"{EventData.Keys.STARTGG_URL} = :startgg_url")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression="SET " + ", ".join(update_expressions),
        ExpressionAttributeValues=expression_values
    )

    no_discord_report = _build_no_discord_report(no_discord_names)

    return ResponseMessage(
        content=f"✅ Event **{startgg_event.event_name}** created with {total_count} registered participants!" + no_discord_report
    )


def update_event_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    event_url = event.get_command_input_value("event_link")
    if not startgg_api.is_valid_startgg_url(event_url):
        return ResponseMessage(
            content="😖 Sorry! This start.gg event link is not valid. "
                    "Make sure it is a link to an event in a tournament like this: "
                    "https://www.start.gg/tournament/midweek-melting/event/mbaacc-double-elim"
        )

    startgg_event = startgg_api.query_startgg_event(event_url)

    if not startgg_event.start_time_utc or not startgg_event.end_time_utc:
        return ResponseMessage(
            content="😔 Could not retrieve start/end times from this start.gg event. "
                    "Please update the event manually with `/event-update`."
        )

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    update_event_record(
        server_id=server_id,
        event_id=event_id,
        record=EventRecord(
            name=startgg_event.event_name,
            location=startgg_event.location or "Online",
            start_time_utc=startgg_event.start_time_utc,
            end_time_utc=startgg_event.end_time_utc,
        ),
        table=aws_services.dynamodb_table
    )

    total_count = len(startgg_event.participants) + len(startgg_event.no_discord_participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]

    update_expressions = [f"{EventData.Keys.STARTGG_URL} = :startgg_url"]
    expression_values = {":startgg_url": event_url}

    if startgg_event.participants:
        startgg_participants_data = {
            participant.user_id: participant.to_dict()
            for participant in startgg_event.participants
        }
        update_expressions.append(f"{EventData.Keys.REGISTERED} = :startgg_registered")
        expression_values[":startgg_registered"] = startgg_participants_data

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression="SET " + ", ".join(update_expressions),
        ExpressionAttributeValues=expression_values
    )

    no_discord_report = _build_no_discord_report(no_discord_names)

    return ResponseMessage(
        content=f"✅ Event **{startgg_event.event_name}** updated with {total_count} registered participants!" + no_discord_report
    )


def event_refresh_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.startgg_url:
        return ResponseMessage(
            content="😔 This event has no start.gg link. "
                    "Use `/event-update-startgg` to link a start.gg event first."
        )

    startgg_event = startgg_api.query_startgg_event(event_data_result.startgg_url)
    total_count = len(startgg_event.participants) + len(startgg_event.no_discord_participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]

    if total_count == 0:
        return ResponseMessage(
            content="😔 No registered participants found for this start.gg event."
        )

    if startgg_event.participants:
        startgg_participants_data = {
            participant.user_id: participant.to_dict()
            for participant in startgg_event.participants
        }
        aws_services.dynamodb_table.update_item(
            Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
            UpdateExpression=f"SET {EventData.Keys.REGISTERED} = :startgg_registered",
            ExpressionAttributeValues={":startgg_registered": startgg_participants_data}
        )

    no_discord_report = _build_no_discord_report(no_discord_names)

    return ResponseMessage(
        content=f"👍 Updated registered list with {total_count} participants from start.gg!" + no_discord_report
    )


def events_list(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    events = db_helper.get_events_for_server(server_id, aws_services.dynamodb_table)

    if not events:
        return ResponseMessage(
            content="ℹ️ No events found for this server."
        )

    lines = ["📅 **Events:**"]
    for i, (name, _event_id) in enumerate(events, 1):
        lines.append(f"{i}. {name}")

    return ResponseMessage(content="\n".join(lines))


def _build_no_discord_report(no_discord_names: list) -> str:
    if not no_discord_names:
        return ""
    participant_list_markdown = "\n".join([f"* {name}" for name in no_discord_names])
    return (
        "\n**I found these start.gg users do not have Discord linked**\n"
        "---\n"
        f"{participant_list_markdown}"
    )
