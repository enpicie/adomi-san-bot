import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import commands.setup.server_commands as setup
from enums import EventMode
from commands.models.response_message import ResponseMessage


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------

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


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------

def test_setup_server_when_config_already_exists(monkeypatch):
    """Returns expected message when server config record already exists."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Mock db_helper to simulate existing config record
    monkeypatch.setattr(setup.db_helper, "get_server_config",
                        lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "already set up" in response.content
    mock_table.put_item.assert_not_called()


# ----------------------------------------------------
#  Default setup flow
# ----------------------------------------------------

def test_setup_server_creates_config_and_server(monkeypatch):
    """Test setup creates CONFIG + SERVER records."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Provide permissions
    mock_event.get_user_permission_int.return_value = (1 << 5)

    monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
    monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    response = setup.setup_server(mock_event, mock_table)

    pk = "SERVER#123"

    # Should call put_item twice (CONFIG + SERVER)
    assert mock_table.put_item.call_count == 2

    # First call: CONFIG record
    config_call = mock_table.put_item.call_args_list[0]
    config_item = config_call.kwargs["Item"]
    assert config_item == {
        "PK": pk,
        "SK": setup.SK_CONFIG,
        "event_mode": EventMode.SERVER_WIDE.value # Excpect default value until PER_CHANNEL implemented.
    }

    # Second call: SERVER record
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
