import commands.register.register_constants as register_constants
import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.registered_participant import RegisteredParticipant

MANUAL_SOURCE = "manual"


def register_user(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")
    target_user_id = event.get_command_input_value("user")

    if target_user_id:
        error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
        if error_message:
            return error_message

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if not event_data_result.register_enabled:
        return ResponseMessage(
            content="😵‍💫 Registration is not open for this event.\n"
                    "An Organizer must open registration before new registrations can be accepted."
        )

    if target_user_id:
        user_id = target_user_id
        resolved_users = event.event_body.get("data", {}).get("resolved", {}).get("users", {})
        resolved_user = resolved_users.get(user_id, {})
        display_name = resolved_user.get("global_name") or resolved_user.get("username") or user_id
    else:
        user_id = event.get_user_id()
        display_name = event.get_username()

    if user_id in event_data_result.registered:
        existing = RegisteredParticipant.from_dynamodb(event_data_result.registered[user_id])
        already_msg = (
            f"✅ {message_helper.get_user_ping(user_id)} is already registered ({existing.get_relative_time_added().lower()})."
            if target_user_id
            else f"✅ You are already registered ({existing.get_relative_time_added().lower()})."
        )
        return ResponseMessage(content=already_msg).with_silent_pings()

    participant = RegisteredParticipant(
        display_name=display_name,
        user_id=user_id,
        source=MANUAL_SOURCE
    )

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.REGISTERED}.#uid = :participant_info",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":participant_info": participant.to_dict()}
    )

    return ResponseMessage(
        content=f"✅ {message_helper.get_user_ping(user_id)} has been registered!"
    )


def register_remove(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")
    user_id = event.get_command_input_value("user")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    if user_id not in event_data_result.registered:
        return ResponseMessage(
            content=f"⚠️ {message_helper.get_user_ping(user_id)} is not registered for this event."
        ).with_silent_pings()

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"REMOVE {EventData.Keys.REGISTERED}.#uid",
        ExpressionAttributeNames={"#uid": user_id}
    )

    return ResponseMessage(
        content=f"✅ {message_helper.get_user_ping(user_id)} has been removed from the registered list."
    ).with_silent_pings()


def toggle_register(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    register_state = event.get_command_input_value("state")
    should_enable = register_state == register_constants.START_PARAM
    print(f"{EventData.Keys.REGISTER_ENABLED}: {should_enable} via input {register_state}")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.REGISTER_ENABLED} = :enable",
        ExpressionAttributeValues={":enable": should_enable}
    )

    content = (
        "🟢 Registration started! Participants can begin registering with `/register`"
        if should_enable
        else "🔴 Registration closed! Registrations will no longer be accepted."
    )

    return ResponseMessage(content=content)
