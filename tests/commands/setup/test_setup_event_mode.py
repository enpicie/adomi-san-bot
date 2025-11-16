import pytest
from unittest.mock import MagicMock

import commands.setup.server_commands as setup
from commands.models.response_message import ResponseMessage
from enums import EventMode


def _make_event(event_mode=None):
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    mock_event.get_command_input_value.return_value = event_mode
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------

def test_setup_event_mode_insufficient_permissions(monkeypatch):
    """Users without Manage Server permission should not be allowed."""
    mock_table = MagicMock()
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = 0  # No permissions

    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_event_mode(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


def test_setup_event_mode_insufficient_permissions_even_if_config_exists(monkeypatch):
    """Even if config exists, permission check should run first."""
    mock_table = MagicMock()
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = 0  # Still no permissions

    monkeypatch.setattr(setup.db_helper, "get_server_config",
                        lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_event_mode(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------

def test_setup_event_mode_config_missing(monkeypatch):
    """Returns expected message when CONFIG does not exist."""
    mock_table = MagicMock()
    mock_event = _make_event(EventMode.PER_CHANNEL.value)

    mock_event.get_user_permission_int.return_value = (1 << 5)  # Has Manage Server

    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_event_mode(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "not set up" in response.content
    assert "setup-server" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  Successful Update Tests
# ----------------------------------------------------

def test_setup_event_mode_updates_existing_config(monkeypatch):
    """Updates event_mode on an existing CONFIG record."""
    mock_table = MagicMock()
    event_mode = EventMode.PER_CHANNEL.value
    mock_event = _make_event(event_mode)

    mock_event.get_user_permission_int.return_value = (1 << 5)  # Has Manage Server

    monkeypatch.setattr(setup.db_helper, "get_server_config",
                        lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG", "event_mode": "server-wide"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_event_mode(mock_event, mock_table)

    pk = "SERVER#123"

    # Ensure update_item was called correctly
    mock_table.update_item.assert_called_once()
    call_kwargs = mock_table.update_item.call_args.kwargs

    assert call_kwargs["Key"] == {"PK": pk, "SK": setup.SK_CONFIG}
    assert call_kwargs["UpdateExpression"] == "SET event_mode = :m"
    assert call_kwargs["ExpressionAttributeValues"] == {":m": event_mode}

    # Verify response
    assert isinstance(response, ResponseMessage)
    assert "Changed event mode" in response.content
    assert event_mode in response.content


def test_setup_event_mode_updates_to_serverwide(monkeypatch):
    """Updates event_mode to server-wide when that's the provided input."""
    mock_table = MagicMock()
    event_mode = EventMode.SERVER_WIDE.value
    mock_event = _make_event(event_mode)

    mock_event.get_user_permission_int.return_value = (1 << 5)

    monkeypatch.setattr(setup.db_helper, "get_server_config",
                        lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_event_mode(mock_event, mock_table)

    pk = "SERVER#123"

    mock_table.update_item.assert_called_once()
    call_kwargs = mock_table.update_item.call_args.kwargs

    assert call_kwargs["Key"] == {"PK": pk, "SK": setup.SK_CONFIG}
    assert call_kwargs["ExpressionAttributeValues"] == {":m": event_mode}

    assert isinstance(response, ResponseMessage)
    assert event_mode in response.content
