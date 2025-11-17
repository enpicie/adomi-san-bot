import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import constants
import commands.setup.data_config_commands as data_config_commands
from commands.models.response_message import ResponseMessage
import database.event_data_keys as event_data_keys
import utils.permissions_helper as permissions_helper
import database.dynamodb_queries as db_helper
from aws_services import AWSServices


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    return mock_event


# ----------------------------------------------------
#  Permissions Tests
# ----------------------------------------------------
def test_set_participant_role_insufficient_permissions():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = 0
    permissions_helper.has_manage_server_permission = lambda perms: False

    response = data_config_commands.set_participant_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


def test_set_participant_role_insufficient_permissions_even_if_config_exists():
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = 0
    permissions_helper.has_manage_server_permission = lambda perms: False

    mock_table.get_item.return_value = {"Item": {"PK": "SERVER#123", "SK": constants.SK_CONFIG}}

    response = data_config_commands.set_participant_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "Manage Server" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  CONFIG existence tests
# ----------------------------------------------------
def test_set_participant_role_when_config_does_not_exist(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = (1 << 5)
    permissions_helper.has_manage_server_permission = lambda perms: True
    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, aws_services: None)

    response = data_config_commands.set_participant_role(mock_event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "This server is not set up" in response.content
    mock_table.update_item.assert_not_called()


# ----------------------------------------------------
#  Successful update flow
# ----------------------------------------------------
def test_set_participant_role_updates_config(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = (1 << 5)
    permissions_helper.has_manage_server_permission = lambda perms: True

    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, aws_services: {"PK": "SERVER#123", "SK": constants.SK_CONFIG})
    mock_event.get_command_input_value.side_effect = lambda key: "Role123" if key == "participant_role" else False

    response = data_config_commands.set_participant_role(mock_event, aws_services)

    mock_table.update_item.assert_called_once()
    call = mock_table.update_item.call_args.kwargs
    assert call["Key"] == {"PK": "SERVER#123", "SK": constants.SK_SERVER}
    assert call["UpdateExpression"] == f"SET {event_data_keys.PARTICIPANT_ROLE} = :r"
    assert call["ExpressionAttributeValues"] == {":r": "Role123"}

    assert isinstance(response, ResponseMessage)
    assert "updated successfully" in response.content


# ----------------------------------------------------
#  Removal flow
# ----------------------------------------------------
def test_set_participant_role_removes_role(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = (1 << 5)
    permissions_helper.has_manage_server_permission = lambda perms: True

    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, aws_services: {"PK": "SERVER#123", "SK": constants.SK_CONFIG})
    mock_event.get_command_input_value.side_effect = lambda key: True if key == "remove_role" else "Role123"

    response = data_config_commands.set_participant_role(mock_event, aws_services)

    mock_table.update_item.assert_called_once()
    call = mock_table.update_item.call_args.kwargs
    assert call["ExpressionAttributeValues"] == {":r": ""}

    assert isinstance(response, ResponseMessage)
    assert "removed successfully" in response.content


# ----------------------------------------------------
#  DB Exception Handling
# ----------------------------------------------------
def test_set_participant_role_raises_on_client_error(monkeypatch):
    mock_table = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=MagicMock())
    mock_event = _make_event()

    mock_event.get_user_permission_int.return_value = (1 << 5)
    permissions_helper.has_manage_server_permission = lambda perms: True

    monkeypatch.setattr(db_helper, "get_server_config", lambda sid, aws_services: {"PK": "SERVER#123", "SK": constants.SK_CONFIG})
    mock_event.get_command_input_value.side_effect = lambda key: "Role123"

    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        data_config_commands.set_participant_role(mock_event, aws_services)
