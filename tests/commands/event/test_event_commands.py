import unittest
from unittest.mock import Mock, patch

from commands.models.response_message import ResponseMessage
from commands.event.event_commands import (
    create_event,
    update_event,
    delete_event,
    create_event_startgg,
    update_event_startgg,
    event_refresh_startgg,
    events_list,
)
from commands.event.startgg.models.startgg_event import StartggEvent
from database.models.event_data import EventData
from database.models.registered_participant import RegisteredParticipant
from database.models.participant import Participant


VALID_URL = "https://www.start.gg/tournament/midweek-melting/event/main-bracket"
INVALID_URL = "https://bad-url.com/not-startgg"


def _make_server_config(organizer_role="ROLE_ORG", default_participant_role=None):
    config = Mock()
    config.organizer_role = organizer_role
    config.default_participant_role = default_participant_role
    return config


def _make_event_item(registered=None, startgg_url=None):
    return {
        EventData.Keys.REGISTERED: registered if registered is not None else {},
        EventData.Keys.CHECKED_IN: {},
        EventData.Keys.QUEUE: {},
        EventData.Keys.PARTICIPANT_ROLE: "",
        EventData.Keys.CHECK_IN_ENABLED: False,
        EventData.Keys.REGISTER_ENABLED: True,
        EventData.Keys.START_MESSAGE: "",
        EventData.Keys.END_MESSAGE: "",
        EventData.Keys.STARTGG_URL: startgg_url,
    }


def _make_aws(event_item=None):
    aws = Mock()
    aws.dynamodb_table.get_item.return_value = (
        {"Item": event_item} if event_item is not None else {}
    )
    return aws


def _make_event(server_id="S1", event_name="evt-1", event_link=VALID_URL, new_name=None,
                event_location="Venue", start_time="2026-01-01 18:00", end_time="2026-01-01 22:00",
                timezone="UTC"):
    event = Mock()
    event.get_server_id.return_value = server_id

    def get_command_input_value(key):
        return {
            "event_name": event_name,
            "event_link": event_link,
            "new_name": new_name,
            "event_location": event_location,
            "start_time": start_time,
            "end_time": end_time,
            "timezone": timezone,
            "event_description": None,
        }.get(key)

    event.get_command_input_value.side_effect = get_command_input_value
    return event


def _make_startgg_event(
    event_name="Main Bracket",
    start_time_utc="2026-03-01T18:00:00Z",
    location="Venue Hall",
    participants=None,
    no_discord_participants=None,
):
    return StartggEvent(
        tourney_name="Midweek Melting",
        event_name=event_name,
        start_time_utc=start_time_utc,
        location=location,
        participants=participants or [],
        no_discord_participants=no_discord_participants or [],
    )


class TestCreateEvent(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = create_event(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_success_calls_create_and_returns_confirmation(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1") as mock_create, \
             patch("commands.event.event_commands.to_utc_iso", return_value="2026-01-01T18:00:00Z"):
            result = create_event(_make_event(event_name="Spring Smash"), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Spring Smash", result.content)
        mock_create.assert_called_once()


class TestDeleteEvent(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = delete_event(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_success_calls_delete_and_returns_confirmation(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.event_commands.delete_event_record") as mock_delete:
            result = delete_event(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("deleted", result.content.lower())
        mock_delete.assert_called_once()


class TestUpdateEvent(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = update_event(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None):
            result = update_event(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_success_calls_update_and_returns_confirmation(self):
        item = _make_event_item()
        aws = _make_aws(event_item=item)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.event_commands.update_event_record") as mock_update:
            result = update_event(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("updated", result.content.lower())
        mock_update.assert_called_once()

    def test_new_name_used_when_provided(self):
        item = _make_event_item()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.event_commands.update_event_record") as mock_update:
            update_event(_make_event(new_name="Renamed Event"), _make_aws(event_item=item))
        record_arg = mock_update.call_args.kwargs["record"]
        self.assertEqual(record_arg.name, "Renamed Event")

    def test_original_name_used_when_new_name_not_provided(self):
        item = _make_event_item()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.event_commands.update_event_record") as mock_update, \
             patch("commands.event.event_commands.to_utc_iso", return_value="2026-01-01T18:00:00Z"):
            update_event(_make_event(event_name="evt-1", new_name=None), _make_aws(event_item=item))
        record_arg = mock_update.call_args.kwargs["record"]
        # new_name is None, so it falls back to event_name autocomplete value (event_id)
        self.assertEqual(record_arg.name, "evt-1")


class TestCreateEventStartgg(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_invalid_url_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None):
            result = create_event_startgg(_make_event(event_link=INVALID_URL), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not valid", result.content)

    def test_missing_start_time_returns_error(self):
        startgg_event = _make_startgg_event(start_time_utc=None)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("start time", result.content)

    def test_success_no_participants(self):
        startgg_event = _make_startgg_event()
        aws = _make_aws()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Main Bracket", result.content)
        self.assertIn("0 registered", result.content)

    def test_success_reports_total_including_no_discord(self):
        participants = [RegisteredParticipant(display_name="P1", user_id="U1", source="startgg")]
        no_discord = [Participant(display_name="P2", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=participants, no_discord_participants=no_discord)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIn("2 registered", result.content)

    def test_success_stores_startgg_url(self):
        startgg_event = _make_startgg_event()
        aws = _make_aws()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            create_event_startgg(_make_event(event_link=VALID_URL), aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn(":startgg_url", call_kwargs["ExpressionAttributeValues"])
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":startgg_url"], VALID_URL)

    def test_success_includes_no_discord_report(self):
        no_discord = [Participant(display_name="NoDiscordGuy", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIn("NoDiscordGuy", result.content)
        self.assertIn("do not have Discord linked", result.content)

    def test_no_discord_participants_stored_keyed_by_display_name(self):
        no_discord = [Participant(display_name="NoDiscordGuy", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        aws = _make_aws()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            create_event_startgg(_make_event(), aws)
        registered = aws.dynamodb_table.update_item.call_args.kwargs["ExpressionAttributeValues"][":startgg_registered"]
        self.assertIn("NoDiscordGuy", registered)
        self.assertEqual(registered["NoDiscordGuy"][Participant.Keys.USER_ID], Participant.DEFAULT_ID_PLACEHOLDER)

    def test_only_no_discord_participants_still_writes_registered(self):
        no_discord = [Participant(display_name="OfflineOnly", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=[], no_discord_participants=no_discord)
        aws = _make_aws()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            create_event_startgg(_make_event(), aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn(":startgg_registered", call_kwargs["ExpressionAttributeValues"])


class TestUpdateEventStartgg(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = update_event_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_invalid_url_returns_error(self):
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None):
            result = update_event_startgg(_make_event(event_link=INVALID_URL), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not valid", result.content)

    def test_missing_start_time_returns_error(self):
        startgg_event = _make_startgg_event(start_time_utc=None)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = update_event_startgg(_make_event(), _make_aws())
        self.assertIn("start time", result.content)

    def test_event_not_found_returns_error(self):
        startgg_event = _make_startgg_event()
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = update_event_startgg(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_success_updates_event_and_reports_total(self):
        participants = [RegisteredParticipant(display_name="P1", user_id="U1", source="startgg")]
        no_discord = [Participant(display_name="P2", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=participants, no_discord_participants=no_discord)
        aws = _make_aws(event_item=_make_event_item())
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.update_event_record"):
            result = update_event_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("updated", result.content.lower())
        self.assertIn("2 registered", result.content)

    def test_success_stores_startgg_url(self):
        startgg_event = _make_startgg_event()
        aws = _make_aws(event_item=_make_event_item())
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.update_event_record"):
            update_event_startgg(_make_event(event_link=VALID_URL), aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":startgg_url"], VALID_URL)

    def test_success_includes_no_discord_report(self):
        no_discord = [Participant(display_name="OffGridPlayer", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.update_event_record"):
            result = update_event_startgg(_make_event(), _make_aws(event_item=_make_event_item()))
        self.assertIn("OffGridPlayer", result.content)

    def test_no_discord_participants_stored_keyed_by_display_name(self):
        no_discord = [Participant(display_name="OffGridPlayer", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        aws = _make_aws(event_item=_make_event_item())
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.update_event_record"):
            update_event_startgg(_make_event(), aws)
        registered = aws.dynamodb_table.update_item.call_args.kwargs["ExpressionAttributeValues"][":startgg_registered"]
        self.assertIn("OffGridPlayer", registered)
        self.assertEqual(registered["OffGridPlayer"][Participant.Keys.USER_ID], Participant.DEFAULT_ID_PLACEHOLDER)

    def test_only_no_discord_participants_still_writes_registered(self):
        no_discord = [Participant(display_name="OfflineOnly", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=[], no_discord_participants=no_discord)
        aws = _make_aws(event_item=_make_event_item())
        with patch("commands.event.event_commands.db_helper.get_server_config_or_fail", return_value=_make_server_config()), \
             patch("commands.event.event_commands.permissions_helper.require_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.update_event_record"):
            update_event_startgg(_make_event(), aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn(":startgg_registered", call_kwargs["ExpressionAttributeValues"])


class TestEventRefreshStartgg(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = event_refresh_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = event_refresh_startgg(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_no_startgg_url_returns_error(self):
        item = _make_event_item(startgg_url=None)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = event_refresh_startgg(_make_event(), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no start.gg link", result.content)

    def test_no_participants_returns_error(self):
        item = _make_event_item(startgg_url=VALID_URL)
        startgg_event = _make_startgg_event(participants=[], no_discord_participants=[])
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), _make_aws(event_item=item))
        self.assertIn("No registered participants", result.content)

    def test_success_with_participants_updates_registered(self):
        item = _make_event_item(startgg_url=VALID_URL)
        participants = [
            RegisteredParticipant(display_name="Player1", user_id="U1", source="startgg"),
            RegisteredParticipant(display_name="Player2", user_id="U2", source="startgg"),
        ]
        startgg_event = _make_startgg_event(participants=participants)
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("2 participants", result.content)
        aws.dynamodb_table.update_item.assert_called_once()

    def test_success_reports_total_including_no_discord(self):
        item = _make_event_item(startgg_url=VALID_URL)
        participants = [RegisteredParticipant(display_name="P1", user_id="U1", source="startgg")]
        no_discord = [Participant(display_name="P2", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=participants, no_discord_participants=no_discord)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), _make_aws(event_item=item))
        self.assertIn("2 participants", result.content)

    def test_success_includes_no_discord_report(self):
        item = _make_event_item(startgg_url=VALID_URL)
        no_discord = [Participant(display_name="OffGridPlayer", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), _make_aws(event_item=item))
        self.assertIn("OffGridPlayer", result.content)

    def test_no_discord_participants_stored_keyed_by_display_name(self):
        item = _make_event_item(startgg_url=VALID_URL)
        no_discord = [Participant(display_name="OffGridPlayer", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            event_refresh_startgg(_make_event(), aws)
        registered = aws.dynamodb_table.update_item.call_args.kwargs["ExpressionAttributeValues"][":startgg_registered"]
        self.assertIn("OffGridPlayer", registered)
        self.assertEqual(registered["OffGridPlayer"][Participant.Keys.USER_ID], Participant.DEFAULT_ID_PLACEHOLDER)

    def test_only_no_discord_participants_still_writes_registered(self):
        item = _make_event_item(startgg_url=VALID_URL)
        no_discord = [Participant(display_name="OfflineOnly", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(participants=[], no_discord_participants=no_discord)
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            event_refresh_startgg(_make_event(), aws)
        aws.dynamodb_table.update_item.assert_called_once()
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn(":startgg_registered", call_kwargs["ExpressionAttributeValues"])

    def test_uses_stored_url_not_command_input(self):
        stored_url = "https://www.start.gg/tournament/stored-event/event/stored-bracket"
        item = _make_event_item(startgg_url=stored_url)
        startgg_event = _make_startgg_event()
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event) as mock_query:
            event_refresh_startgg(_make_event(), _make_aws(event_item=item))
        mock_query.assert_called_once_with(stored_url)


class TestEventsList(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = events_list(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_no_events_returns_info(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("database.dynamodb_utils.get_events_for_server", return_value=[]):
            result = events_list(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("No events", result.content)

    def test_events_listed_with_names(self):
        mock_events = [("Summer Smash", "EVT1"), ("Winter Bout", "EVT2")]
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("database.dynamodb_utils.get_events_for_server", return_value=mock_events):
            result = events_list(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Summer Smash", result.content)
        self.assertIn("Winter Bout", result.content)


if __name__ == "__main__":
    unittest.main()
