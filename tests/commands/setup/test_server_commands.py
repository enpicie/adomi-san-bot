import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import commands.setup.server_commands as setup
from commands.models.response_message import ResponseMessage
from enums import EventMode


def _make_event(event_mode=None):
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    mock_event.get_command_input_value.return_value = event_mode
    return mock_event

def test_setup_server_insufficient_permissions(monkeypatch):
    """Users without Manage Server permission should not be allowed."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # User has NO permissions
    mock_event.get_user_permission_int.return_value = 0

    # Ensure DB is never touched
    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.put_item.assert_not_called()


def test_setup_server_insufficient_permissions_even_if_config_exists(monkeypatch):
    """Even if CONFIG already exists, permissions should be checked first."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # User still has NO permissions
    mock_event.get_user_permission_int.return_value = 0

    # Simulate config exists — should NOT matter because perms fail first
    monkeypatch.setattr(setup.db_helper, "get_server_config",
                        lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.put_item.assert_not_called()


def test_setup_server_when_config_already_exists(monkeypatch):
    """Test returns expected message when server config record already exists."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Mock db_helper to simulate existing config record
    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "already set up" in response.content
    mock_table.put_item.assert_not_called()


def test_setup_server_server_wide(monkeypatch):
    """Test setup creates CONFIG + SERVER records when event_mode is server-wide."""
    mock_table = MagicMock()
    mock_event = _make_event(EventMode.SERVER_WIDE.value)

    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    # Expected DynamoDB PK
    pk = "SERVER#123"

    # Should call put_item twice (CONFIG + SERVER)
    assert mock_table.put_item.call_count == 2

    # Check CONFIG record
    config_call = mock_table.put_item.call_args_list[0]
    config_item = config_call.kwargs["Item"]
    assert config_item == {
        "PK": pk,
        "SK": setup.SK_CONFIG,
        "event_mode": EventMode.SERVER_WIDE.value
    }

    # Check SERVER record
    server_call = mock_table.put_item.call_args_list[1]
    server_item = server_call.kwargs["Item"]
    assert server_item == {
        "PK": pk,
        "SK": setup.SK_SERVER,
        "checked_in": {},
        "queued": {}
    }

    # Verify message
    assert isinstance(response, ResponseMessage)
    assert "Server setup complete" in response.content
    assert EventMode.SERVER_WIDE.value in response.content


def test_setup_server_per_channel(monkeypatch):
    """Test setup creates only CONFIG record when event_mode is per-channel."""
    mock_table = MagicMock()
    mock_event = _make_event(EventMode.PER_CHANNEL.value)

    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    pk = "SERVER#123"

    # Should call put_item once (CONFIG only)
    mock_table.put_item.assert_called_once()
    config_call = mock_table.put_item.call_args
    config_item = config_call.kwargs["Item"]

    assert config_item == {
        "PK": pk,
        "SK": setup.SK_CONFIG,
        "event_mode": EventMode.PER_CHANNEL.value
    }

    # Verify message
    assert isinstance(response, ResponseMessage)
    assert "Server setup complete" in response.content
    assert EventMode.PER_CHANNEL.value in response.content
