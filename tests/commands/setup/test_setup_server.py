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

def test_setup_server_insufficient_permissions():
    """Users without Manage Server permission should not be allowed."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # User has NO permissions
    mock_event.get_user_permission_int.return_value = 0

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.put_item.assert_not_called()


def test_setup_server_insufficient_permissions_even_if_config_exists():
    """
    Even if CONFIG already exists, permissions should be checked first.
    db_helper is not mocked — it must query via real logic.
    """
    mock_table = MagicMock()
    mock_event = _make_event()

    # No perms
    mock_event.get_user_permission_int.return_value = 0

    # Pretend CONFIG exists by making table.get_item return an item
    mock_table.get_item.return_value = {
        "Item": {"PK": "SERVER#123", "SK": setup.SK_CONFIG}
    }

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content

    # Never writes
    mock_table.put_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------

def test_setup_server_when_config_already_exists():
    """Returns expected message when server config record already exists."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Simulate an existing CONFIG record
    mock_table.get_item.return_value = {
        "Item": {"PK": "SERVER#123", "SK": setup.SK_CONFIG}
    }

    response = setup.setup_server(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "already set up" in response.content

    mock_table.put_item.assert_not_called()


# ----------------------------------------------------
#  Default setup flow
# ----------------------------------------------------

def test_setup_server_creates_config_and_server():
    """Test setup creates CONFIG + SERVER records."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Provide Manage Server permission
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # No existing config
    mock_table.get_item.return_value = {}

    response = setup.setup_server(mock_event, mock_table)

    pk = "SERVER#123"

    # Should call put_item twice: CONFIG + SERVER
    assert mock_table.put_item.call_count == 2

    # First call: CONFIG record
    config_call = mock_table.put_item.call_args_list[0]
    assert config_call.kwargs["Item"] == {
        "PK": pk,
        "SK": setup.SK_CONFIG,
        "event_mode": EventMode.SERVER_WIDE.value
    }

    # Second call: SERVER record
    server_call = mock_table.put_item.call_args_list[1]
    assert server_call.kwargs["Item"] == {
        "PK": pk,
        "SK": setup.SK_SERVER,
        "checked_in": {},
        "queued": {}
    }

    assert isinstance(response, ResponseMessage)
    assert "Server setup complete" in response.content
