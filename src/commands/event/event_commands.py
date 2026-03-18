from datetime import datetime, timezone as dt_timezone

import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
import commands.event.startgg.startgg_api as startgg_api
from commands.event.event_helper import EventRecord, create_event_record, update_event_record, delete_event_record
from commands.event.timezone_helper import to_utc_iso
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def _is_past_time(utc_iso: str) -> bool:
    """Returns True if the given UTC ISO 8601 time is before the current time."""
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return dt < datetime.now(dt_timezone.utc)
    except Exception:
        return False


def _resolve_participant_role(event: DiscordEvent, aws_services: AWSServices) -> tuple:
    """
    Returns (server_config, participant_role, no_role_warning).
    server_config may be a ResponseMessage on failure.
    participant_role is the resolved role (input or server default), or None if unset.
    no_role_warning is a string to append to the response if no role is set, or "".
    """
    server_id = event.get_server_id()
    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config, None, ""

    participant_role = (
        event.get_command_input_value("participant_role")
        or server_config.default_participant_role
    )

    no_role_warning = (
        "\n⚠️ No participant role is set for this event. "
        "Use `/event-update` or `/set-default-participant-role` to add one."
        if not participant_role else ""
    )

    return server_config, participant_role, no_role_warning


def create_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config
    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    participant_role = (
        event.get_command_input_value("participant_role")
        or server_config.default_participant_role
    )
    no_role_warning = (
        "\n⚠️ No participant role is set for this event. "
        "Use `/event-update` or `/set-default-participant-role` to add one."
        if not participant_role else ""
    )

    timezone = event.get_command_input_value("timezone")

    create_event_record(
        server_id=server_id,
        record=EventRecord(
            name=event.get_command_input_value("event_name"),
            location=event.get_command_input_value("event_location"),
            start_time_utc=to_utc_iso(event.get_command_input_value("start_time"), timezone),
            end_time_utc=to_utc_iso(event.get_command_input_value("end_time"), timezone),
            description=event.get_command_input_value("event_description"),
            participant_role=participant_role
        ),
        table=aws_services.dynamodb_table
    )

    event_name = event.get_command_input_value("event_name")
    return ResponseMessage(content=f"Event '{event_name}' created successfully.{no_role_warning}")


def update_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config
    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    # Collect inputs — None means "not provided by user"
    new_name = event.get_command_input_value("new_name")
    location_input = event.get_command_input_value("event_location")
    timezone = event.get_command_input_value("timezone")
    start_time_input = event.get_command_input_value("start_time")
    end_time_input = event.get_command_input_value("end_time")
    participant_role_input = event.get_command_input_value("participant_role")

    if (start_time_input or end_time_input) and not timezone:
        return ResponseMessage(content="❌ A timezone is required when providing a start time or end time.")

    # Resolve final values — fall back to stored values for fields not provided
    name = new_name or event_data_result.event_name or event_id
    location = location_input or event_data_result.event_location
    new_start_time_utc = to_utc_iso(start_time_input, timezone) if start_time_input else None
    end_time_utc = to_utc_iso(end_time_input, timezone) if end_time_input else event_data_result.end_time
    # For updates, only change participant_role if explicitly provided — don't apply server default
    participant_role = participant_role_input if participant_role_input else event_data_result.participant_role

    # Detect past start time — warn but don't change it; proceed with other fields
    start_time_changed = new_start_time_utc is not None and new_start_time_utc != event_data_result.start_time
    start_time_in_past = start_time_changed and _is_past_time(new_start_time_utc)
    start_time_utc = (new_start_time_utc if start_time_changed and not start_time_in_past
                      else event_data_result.start_time)

    start_time_updated = update_event_record(
        server_id=server_id,
        event_id=event_id,
        record=EventRecord(
            name=name,
            location=location,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            description=event.get_command_input_value("event_description"),
            participant_role=participant_role
        ),
        table=aws_services.dynamodb_table
    )

    # Build change summary — only report fields that were provided AND differ from stored
    changes = []
    if new_name and new_name != event_data_result.event_name:
        changes.append(f"📝 Name: `{event_data_result.event_name}` → `{new_name}`")
    if location_input and location_input != event_data_result.event_location:
        changes.append(f"📍 Location updated to `{location_input}`")
    if start_time_in_past:
        changes.append(f"⚠️ Start time not updated — `{new_start_time_utc}` is in the past")
    elif start_time_changed:
        if start_time_updated:
            changes.append(f"🕒 Start time updated to `{new_start_time_utc}`")
        else:
            changes.append(f"⚠️ Start time unchanged — event is already active on Discord")
    if end_time_input and end_time_utc != event_data_result.end_time:
        changes.append(f"🔚 End time updated to `{end_time_utc}`")
    if participant_role_input and participant_role_input != event_data_result.participant_role:
        changes.append(f"🎭 Participant role updated")

    no_role_warning = (
        "\n⚠️ No participant role is set for this event. "
        "Use `/event-update` or `/set-default-participant-role` to add one."
        if not participant_role else ""
    )
    startgg_start_note = (
        "\nℹ️ This event is linked to start.gg — use `/event-refresh-startgg` to sync the start time from there."
        if event_data_result.startgg_url and start_time_input else ""
    )

    if not changes:
        return ResponseMessage(content=f"✅ Event updated (no changes detected).{no_role_warning}")

    change_summary = "\n".join(f"• {c}" for c in changes)
    return ResponseMessage(content=f"✅ Event updated:\n{change_summary}{startgg_start_note}{no_role_warning}")


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
    server_id = event.get_server_id()
    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config
    error_message = permissions_helper.require_organizer_role(server_config, event)
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

    if not startgg_event.start_time_utc:
        return ResponseMessage(
            content="😔 Could not retrieve the start time from this start.gg event. "
                    "Please create the event manually with `/event-create`."
        )

    past_time_warning = ""
    start_time_utc = startgg_event.start_time_utc
    if _is_past_time(start_time_utc):
        start_time_utc = datetime.now(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        past_time_warning = (
            f"\n⚠️ The start.gg event time (`{startgg_event.start_time_utc}`) is in the past. "
            "The current time has been used instead."
        )

    participant_role = (
        event.get_command_input_value("participant_role")
        or server_config.default_participant_role
    )
    no_role_warning = (
        "\n⚠️ No participant role is set for this event. "
        "Use `/event-update` or `/set-default-participant-role` to add one."
        if not participant_role else ""
    )

    timezone = event.get_command_input_value("timezone")
    end_time_utc = to_utc_iso(event.get_command_input_value("end_time"), timezone)

    event_id = create_event_record(
        server_id=server_id,
        record=EventRecord(
            name=startgg_event.event_name,
            location=startgg_event.location or "Online",
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            participant_role=participant_role
        ),
        table=aws_services.dynamodb_table
    )

    total_count = len(startgg_event.participants) + len(startgg_event.no_discord_participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]

    all_participants_data = {p.user_id: p.to_dict() for p in startgg_event.participants}
    for p in startgg_event.no_discord_participants:
        all_participants_data[p.display_name] = p.to_dict()

    update_expressions = []
    expression_values = {":startgg_url": event_url}

    if all_participants_data:
        update_expressions.append(f"{EventData.Keys.REGISTERED} = :startgg_registered")
        expression_values[":startgg_registered"] = all_participants_data

    update_expressions.append(f"{EventData.Keys.STARTGG_URL} = :startgg_url")

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression="SET " + ", ".join(update_expressions),
        ExpressionAttributeValues=expression_values
    )

    no_discord_report = _build_no_discord_report(no_discord_names)

    return ResponseMessage(
        content=f"✅ Event **{startgg_event.event_name}** created with {total_count} registered participants!{past_time_warning}{no_discord_report}{no_role_warning}"
    )


def update_event_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config
    error_message = permissions_helper.require_organizer_role(server_config, event)
    if error_message:
        return error_message

    event_id = event.get_command_input_value("event_name")
    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    # event_link is optional — fall back to the stored startgg URL if not provided
    event_url = event.get_command_input_value("event_link")
    if event_url:
        if not startgg_api.is_valid_startgg_url(event_url):
            return ResponseMessage(
                content="😖 Sorry! This start.gg event link is not valid. "
                        "Make sure it is a link to an event in a tournament like this: "
                        "https://www.start.gg/tournament/midweek-melting/event/mbaacc-double-elim"
            )
    else:
        event_url = event_data_result.startgg_url
        if not event_url:
            return ResponseMessage(
                content="😔 This event has no start.gg link. "
                        "Provide an event link to set one."
            )

    startgg_event = startgg_api.query_startgg_event(event_url)

    if not startgg_event.start_time_utc:
        return ResponseMessage(
            content="😔 Could not retrieve the start time from this start.gg event. "
                    "Please update the event manually with `/event-update`."
        )

    timezone = event.get_command_input_value("timezone")
    end_time_utc = to_utc_iso(event.get_command_input_value("end_time"), timezone) or event_data_result.end_time

    # Resolve participant_role: input → existing event role only
    participant_role = (
        event.get_command_input_value("participant_role")
        or event_data_result.participant_role
    )
    no_role_warning = (
        "\n⚠️ No participant role is set for this event. "
        "Use `/event-update` or `/set-default-participant-role` to add one."
        if not participant_role else ""
    )

    # Check if startgg's start time differs and is in the past — warn but don't block
    start_time_changed = startgg_event.start_time_utc != event_data_result.start_time
    start_time_in_past = start_time_changed and _is_past_time(startgg_event.start_time_utc)
    start_time_for_update = (event_data_result.start_time if start_time_in_past
                             else startgg_event.start_time_utc)

    start_time_updated = update_event_record(
        server_id=server_id,
        event_id=event_id,
        record=EventRecord(
            name=startgg_event.event_name,
            location=startgg_event.location or "Online",
            start_time_utc=start_time_for_update,
            end_time_utc=end_time_utc,
            participant_role=participant_role
        ),
        table=aws_services.dynamodb_table
    )

    total_count = len(startgg_event.participants) + len(startgg_event.no_discord_participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]

    all_participants_data = {p.user_id: p.to_dict() for p in startgg_event.participants}
    for p in startgg_event.no_discord_participants:
        all_participants_data[p.display_name] = p.to_dict()

    # Always write both URL and full registrants list
    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.STARTGG_URL} = :startgg_url, {EventData.Keys.REGISTERED} = :startgg_registered",
        ExpressionAttributeValues={":startgg_url": event_url, ":startgg_registered": all_participants_data}
    )

    no_discord_report = _build_no_discord_report(no_discord_names)

    changes = []
    if start_time_in_past:
        changes.append(f"⚠️ Start time not updated — `{startgg_event.start_time_utc}` is in the past")
    elif start_time_changed:
        if start_time_updated:
            changes.append(f"🕒 Start time updated to `{startgg_event.start_time_utc}`")
        else:
            changes.append(f"⚠️ Start time in start.gg (`{startgg_event.start_time_utc}`) differs but could not be updated — event is already active on Discord")
    changes.append(f"👥 Registered list synced with {total_count} participant(s)")
    change_summary = "\n".join(f"• {c}" for c in changes)

    return ResponseMessage(
        content=f"✅ Event **{startgg_event.event_name}** updated from start.gg:\n{change_summary}{no_discord_report}{no_role_warning}"
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

    changes = []

    if startgg_event.start_time_utc:
        start_time_changed = startgg_event.start_time_utc != event_data_result.start_time
        if start_time_changed:
            if _is_past_time(startgg_event.start_time_utc):
                changes.append(f"⚠️ Start time not updated — `{startgg_event.start_time_utc}` is in the past")
            else:
                start_time_updated = update_event_record(
                    server_id=server_id,
                    event_id=event_id,
                    record=EventRecord(
                        name=event_data_result.event_name or event_id,
                        location=event_data_result.event_location or "Online",
                        start_time_utc=startgg_event.start_time_utc,
                        end_time_utc=event_data_result.end_time,
                        participant_role=event_data_result.participant_role
                    ),
                    table=aws_services.dynamodb_table
                )
                if start_time_updated:
                    changes.append(f"🕒 Start time updated to `{startgg_event.start_time_utc}`")
                else:
                    changes.append(f"⚠️ Start time in start.gg (`{startgg_event.start_time_utc}`) differs but could not be updated — event is already active on Discord")

    # Always write the current registrants list (even if empty)
    all_participants_data = {p.user_id: p.to_dict() for p in startgg_event.participants}
    for p in startgg_event.no_discord_participants:
        all_participants_data[p.display_name] = p.to_dict()

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.REGISTERED} = :startgg_registered",
        ExpressionAttributeValues={":startgg_registered": all_participants_data}
    )
    changes.append(f"👥 Registered list updated with {total_count} participant(s)")

    no_discord_report = _build_no_discord_report(no_discord_names)
    change_summary = "\n".join(f"• {c}" for c in changes)

    return ResponseMessage(
        content=f"👍 Event refreshed from start.gg:\n{change_summary}{no_discord_report}"
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
        f"{participant_list_markdown}\n"
        "\n*Please ensure the correct Discord account is linked and set to public on their start.gg profile.*"
    )
