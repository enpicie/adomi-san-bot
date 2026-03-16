import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def show_registered(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.registered:
        return ResponseMessage(
            content="ℹ️ There are currently no registered users."
        )

    content = message_helper.build_participants_list(
        list_header="✅ **Registered Users:**",
        participants=list(event_data_result.registered.values())
    )
    return ResponseMessage(content=content).with_silent_pings()


def clear_registered(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.registered:
        return ResponseMessage(
            content="ℹ️ There are no registered users to clear."
        )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.REGISTERED} = :empty_map",
        ExpressionAttributeValues={":empty_map": {}}
    )

    return ResponseMessage(
        content="😼 All registered users have been cleared!"
    )
