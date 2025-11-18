import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import commands.setup.server_commands as setup
from commands.models.response_message import ResponseMessage


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------

def test_set_organizer_role_insufficient_permissions():
    """Users without Manage Server permission should not be allowed."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # User has no permissions
    mock_event.get_user_permission_int.return_value = 0

    response = setup.set_organizer_role(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content

    # Database should never be written to
    mock_table.update_item.assert_not_called()


def test_set_organizer_role_insufficient_permissions_even_if_config_exists():
    """
    Even if the CONFIG record exists, insufficient permissions should stop the flow
    before any DB calls are made.
    """
    mock_table = MagicMock()
    mock_event = _make_event()

    # No permissions
    mock_event.get_user_permission_int.return_value = 0

    # Pretend CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": setup.SK_CONFIG}}

    response = setup.set_organizer_role(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content

    # Never writes
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------

def test_set_organizer_role_when_config_does_not_exist():
    """Should return setup-required message when CONFIG is missing."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Provide Manage Server permission
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # No CONFIG record
    mock_table.get_item.return_value = {}

    response = setup.set_organizer_role(mock_event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "This server is not set up" in response.content

    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  Successful update flow
# ----------------------------------------------------

def test_set_organizer_role_updates_config():
    """Test that organizer_role is updated when permissions and config are valid."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Permissions OK
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": setup.SK_CONFIG}}

    # Organizer role provided
    mock_event.get_command_input_value.return_value = "Role123"

    response = setup.set_organizer_role(mock_event, mock_table)

    # Validate DB update call
    mock_table.update_item.assert_called_once()
    call = mock_table.update_item.call_args.kwargs

    assert call["Key"] == {"PK": "SERVER#123", "SK": setup.SK_CONFIG}
    assert call["UpdateExpression"] == "SET organizer_role = :r"
    assert call["ExpressionAttributeValues"] == {":r": "Role123"}

    assert isinstance(response, ResponseMessage)
    assert "updated successfully" in response.content


# ----------------------------------------------------
#  DB Exception Handling
# ----------------------------------------------------

def test_set_organizer_role_raises_on_client_error():
    """ClientError during update should bubble upward."""
    mock_table = MagicMock()
    mock_event = _make_event()

    # Valid permission
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": setup.SK_CONFIG}}

    # Organizer role provided
    mock_event.get_command_input_value.return_value = "Role123"

    # Force DynamoDB to raise ClientError
    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        setup.set_organizer_role(mock_event, mock_table)
