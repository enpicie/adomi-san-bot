from commands.event.event_helper import EventRecord, create_event_record, delete_event_record
from commands.event.timezone_helper import to_utc_iso
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def create_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
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


def delete_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    # autocomplete value for event_name is the event_id
    event_id = event.get_command_input_value("event_name")

    delete_event_record(
        server_id=event.get_server_id(),
        event_id=event_id,
        table=aws_services.dynamodb_table
    )

    return ResponseMessage(content=f"Event deleted successfully.")

