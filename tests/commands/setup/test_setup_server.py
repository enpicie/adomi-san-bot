import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import constants
import commands.setup.server_commands as setup
import database.server_config_keys as server_config_keys
import database.event_data_keys as event_data_keys
from enums import EventMode
from commands.models.response_message import ResponseMessage
import database.dynamodb_queries as db_helper
import utils.permissions_helper as permissions_helper


def _make_event():
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    mock_event.get_command_input_value.return_value = "Role123"
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------
def test_setup_server_insufficient_permissions(monkeypatch):
    mock_table = MagicMock()
    mock_event = _make_event()

    monkeypatch.setattr(permissions_helper, "has_manage_server_permission", lambda perms: False)

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.put_item.assert_not_called()


def test_setup_server_insufficient_permissions_even_if_config_exists(monkeypatch):
    mock_table = MagicMock()
    mock_event = _make_event()

    monkeypatch.setattr(permissions_helper, "has_manage_server_permission", lambda perms: False)
    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, table: {"PK": "SERVER#123", "SK": constants.SK_CONFIG})

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.put_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------
def test_setup_server_when_config_already_exists(monkeypatch):
    mock_table = MagicMock()
    mock_event = _make_event()

    monkeypatch.setattr(permissions_helper, "has_manage_server_permission", lambda perms: True)
    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, table: {"PK": "SERVER#123", "SK": constants.SK_CONFIG})

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "already set up" in response.content
    mock_table.put_item.assert_not_called()


# ----------------------------------------------------
#  Default setup flow
# ----------------------------------------------------
def test_setup_server_creates_config_and_server(monkeypatch):
    mock_table = MagicMock()
    mock_event = _make_event()

    monkeypatch.setattr(permissions_helper, "has_manage_server_permission", lambda perms: True)
    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, table: None)
    monkeypatch.setattr(db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    pk = "SERVER#123"

    # Should call put_item twice: CONFIG + SERVER
    assert mock_table.put_item.call_count == 2

    # First call: CONFIG record
    config_call = mock_table.put_item.call_args_list[0]
    assert config_call.kwargs["Item"] == {
        "PK": pk,
        "SK": constants.SK_CONFIG,
        server_config_keys.EVENT_MODE: EventMode.SERVER_WIDE.value,
        server_config_keys.ORGANIZER_ROLE: "Role123"
    }

    # Second call: SERVER record
    server_call = mock_table.put_item.call_args_list[1]
    assert server_call.kwargs["Item"] == {
        "PK": pk,
        "SK": constants.SK_SERVER,
        event_data_keys.CHECKED_IN: {},
        event_data_keys.REGISTERED: {},
        event_data_keys.QUEUE: {}
    }

    assert isinstance(response, ResponseMessage)
    assert "Server setup complete" in response.content
