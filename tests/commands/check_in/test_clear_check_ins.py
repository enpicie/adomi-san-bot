import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import constants
import commands.check_in.check_in_commands as check_in
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
import database.config_data_helper as config_helper
import commands.check_in.queue_role_removal as role_removal_queue
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def _make_event():
    mock_event = MagicMock(spec=DiscordEvent)
    mock_event.get_server_id.return_value = "123"
    mock_event.get_user_roles.return_value = ["roleX"]  # Default roles
    return mock_event


# ----------------------------------------------------
#  User lacks organizer role
# ----------------------------------------------------
def test_clear_check_ins_user_not_organizer(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()

    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: "roleY")
    # event.get_user_roles() returns ["roleX"] by default, so user is not organizer

    response = check_in.clear_check_ins(event, aws_services)

    assert isinstance(response, ResponseMessage)
    assert "don't have permission" in response.content
    mock_table.update_item.assert_not_called()
    mock_queue.send_message_batch.assert_not_called()


# ----------------------------------------------------
#  try_get_organizer_role returns ResponseMessage
# ----------------------------------------------------
def test_clear_check_ins_organizer_role_error(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()

    error_msg = ResponseMessage(content="error retrieving organizer role")
    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: error_msg)

    response = check_in.clear_check_ins(event, aws_services)
    assert response == error_msg
    mock_table.update_item.assert_not_called()
    mock_queue.send_message_batch.assert_not_called()


# ----------------------------------------------------
#  No event data
# ----------------------------------------------------
def test_clear_check_ins_no_event_data(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()

    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: "roleX")
    monkeypatch.setattr(db_helper, "get_server_event_data", lambda sid, table: None)

    response = check_in.clear_check_ins(event, aws_services)
    assert "no check-in data" in response.content
    mock_table.update_item.assert_not_called()
    mock_queue.send_message_batch.assert_not_called()


# ----------------------------------------------------
#  No checked-in users
# ----------------------------------------------------
def test_clear_check_ins_empty_checked_in(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()

    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: "roleX")
    monkeypatch.setattr(db_helper, "get_server_event_data", lambda sid, table: {
        event_data_keys.PARTICIPANT_ROLE: "role123",
        event_data_keys.CHECKED_IN: {}
    })

    response = check_in.clear_check_ins(event, aws_services)
    assert "no checked-in users" in response.content
    mock_table.update_item.assert_not_called()
    mock_queue.send_message_batch.assert_not_called()


# ----------------------------------------------------
#  Successful clear
# ----------------------------------------------------
def test_clear_check_ins_happy_path(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()
    event.get_user_roles.return_value = ["roleX"]  # user has organizer role

    checked_in_data = {"user1": {}, "user2": {}}
    participant_role = "role123"

    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: "roleX")
    monkeypatch.setattr(db_helper, "get_server_event_data", lambda sid, table: {
        event_data_keys.PARTICIPANT_ROLE: participant_role,
        event_data_keys.CHECKED_IN: checked_in_data
    })

    mock_enqueue = MagicMock()
    monkeypatch.setattr(role_removal_queue, "enqueue_remove_role_jobs", mock_enqueue)

    response = check_in.clear_check_ins(event, aws_services)

    pk = f"SERVER#{event.get_server_id()}"
    sk = constants.SK_SERVER
    mock_table.update_item.assert_called_once_with(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET checked_in = :empty_map",
        ExpressionAttributeValues={":empty_map": {}}
    )

    mock_enqueue.assert_called_once_with(
        server_id=event.get_server_id(),
        user_ids=list(checked_in_data.keys()),
        role_id=participant_role,
        sqs_queue=mock_queue
    )

    assert "All check-ins have been cleared" in response.content


# ----------------------------------------------------
#  ClientError propagation
# ----------------------------------------------------
def test_clear_check_ins_client_error(monkeypatch):
    mock_table = MagicMock()
    mock_queue = MagicMock()
    aws_services = AWSServices(table=mock_table, remove_role_sqs_queue=mock_queue)
    event = _make_event()
    event.get_user_roles.return_value = ["roleX"]

    checked_in_data = {"user1": {}}
    monkeypatch.setattr(config_helper, "try_get_organizer_role", lambda sid, table: "roleX")
    monkeypatch.setattr(db_helper, "get_server_event_data", lambda sid, table: {
        event_data_keys.PARTICIPANT_ROLE: "role123",
        event_data_keys.CHECKED_IN: checked_in_data
    })

    mock_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}}, "UpdateItem"
    )

    with pytest.raises(ClientError):
        check_in.clear_check_ins(event, aws_services)
