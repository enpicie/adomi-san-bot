import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import constants
import commands.setup.server_commands as setup
from commands.models.response_message import ResponseMessage
import database.server_config_keys as server_config_keys
from aws_services import AWSServices


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------

def test_set_organizer_role_insufficient_permissions():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    # User has no permissions
    mock_event.get_user_permission_int.return_value = 0

    response = setup.set_organizer_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


def test_set_organizer_role_insufficient_permissions_even_if_config_exists():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = 0

    # Pretend CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": constants.SK_CONFIG}}

    response = setup.set_organizer_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------

def test_set_organizer_role_when_config_does_not_exist():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    # Provide Manage Server permission
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # No CONFIG record
    mock_table.get_item.return_value = {}

    response = setup.set_organizer_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "This server is not set up" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  Successful update flow
# ----------------------------------------------------

def test_set_organizer_role_updates_config():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    # Permissions OK
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": constants.SK_CONFIG}}

    # Organizer role provided
    mock_event.get_command_input_value.return_value = "Role123"

    response = setup.set_organizer_role(mock_event, aws_services)

    # Validate DB update call
    mock_table.update_item.assert_called_once()
    call = mock_table.update_item.call_args.kwargs
    assert call["Key"] == {"PK": "SERVER#123", "SK": constants.SK_CONFIG}
    assert call["UpdateExpression"] == f"SET {server_config_keys.ORGANIZER_ROLE} = :r"
    assert call["ExpressionAttributeValues"] == {":r": "Role123"}

    assert isinstance(response, ResponseMessage)
    assert "updated successfully" in response.content


# ----------------------------------------------------
#  DB Exception Handling
# ----------------------------------------------------

def test_set_organizer_role_raises_on_client_error():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    # Valid permission
    mock_event.get_user_permission_int.return_value = (1 << 5)

    # CONFIG exists
    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": constants.SK_CONFIG}}

    # Organizer role provided
    mock_event.get_command_input_value.return_value = "Role123"

    # Force DynamoDB to raise ClientError
    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        setup.set_organizer_role(mock_event, aws_services)
