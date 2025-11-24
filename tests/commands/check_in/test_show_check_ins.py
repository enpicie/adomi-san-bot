import pytest
from unittest.mock import MagicMock

import commands.check_in.check_in_commands as check_in
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def _make_event():
    mock_event = MagicMock(spec=DiscordEvent)
    mock_event.get_server_id.return_value = "123"
    return mock_event


# ----------------------------------------------------
#  No event data
# ----------------------------------------------------
def test_show_check_ins_no_event_data(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    event = _make_event()

    # Simulate no event data in DB
    monkeypatch.setattr(
        db_helper, "get_server_event_data", lambda sid, table: None
    )

    response = check_in.show_check_ins(event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "no check-in data" in response.content.lower()
    assert "setup-server" in response.content.lower()


# ----------------------------------------------------
#  No checked-in users
# ----------------------------------------------------
def test_show_check_ins_empty_checked_in(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    event = _make_event()

    monkeypatch.setattr(
        db_helper,
        "get_server_event_data",
        lambda sid, table: {
            event_data_keys.CHECKED_IN: {}
        }
    )

    response = check_in.show_check_ins(event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "no checked-in users" in response.content.lower()


# ----------------------------------------------------
#  Show list of checked-in users
# ----------------------------------------------------
def test_show_check_ins_happy_path(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    event = _make_event()

    checked_in_data = {
        "user1": {"display_name": "Alice"},
        "user2": {"display_name": "Bob"},
    }

    monkeypatch.setattr(
        db_helper,
        "get_server_event_data",
        lambda sid, table: {
            event_data_keys.CHECKED_IN: checked_in_data
        }
    )

    response = check_in.show_check_ins(event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "checked-in users" in response.content.lower()

    # Validate ordered list content
    assert "- Alice" in response.content
    assert "- Bob" in response.content
