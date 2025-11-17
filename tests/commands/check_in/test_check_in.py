import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import commands.check_in.check_in_commands as check_in
from commands.models.response_message import ResponseMessage
import utils.message_helper as msg_helper


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    mock_event.get_channel_id.return_value = "10"
    mock_event.get_user_id.return_value = "456"
    mock_event.get_username.return_value = "Alice"
    return mock_event


# ----------------------------------------------------
#  Successful check-in
# ----------------------------------------------------
def test_check_in_user_success(monkeypatch):
    """Test a successful check-in calls update_item and returns expected message."""
    mock_table = MagicMock()
    event = _make_event()

    # Mock user ping helper
    monkeypatch.setattr(msg_helper, "get_user_ping", lambda uid: f"<@{uid}>")

    response = check_in.check_in_user(event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert response.content == "✅ Checked in <@456>!"

    pk = f"SERVER#{event.get_server_id()}"
    sk = "SERVER"
    user_id = event.get_user_id()
    username = event.get_username()

    # Verify correct update_item call
    mock_table.update_item.assert_called_once()
    args, kwargs = mock_table.update_item.call_args
    assert kwargs["Key"] == {"PK": pk, "SK": sk}
    assert kwargs["ExpressionAttributeNames"] == {"#uid": user_id}
    assert kwargs["ExpressionAttributeValues"][":participant_info"]["user_id"] == user_id
    assert kwargs["ExpressionAttributeValues"][":participant_info"]["display_name"] == username
    assert kwargs["ConditionExpression"] == "attribute_exists(PK)"


# ----------------------------------------------------
#  Conditional check failure
# ----------------------------------------------------
def test_check_in_user_conditional_check_failed(monkeypatch):
    """If the channel record doesn't exist, should return proper message."""
    mock_table = MagicMock()
    event = _make_event()

    # Simulate DynamoDB conditional check failure
    error_response = {
        "Error": {"Code": "ConditionalCheckFailedException", "Message": "Record does not exist"}
    }
    mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

    response = check_in.check_in_user(event, mock_table)

    assert isinstance(response, ResponseMessage)
    assert "has not been set up yet" in response.content
    mock_table.update_item.assert_called_once()


# ----------------------------------------------------
#  Unexpected ClientError
# ----------------------------------------------------
def test_check_in_user_unexpected_client_error():
    """Any unexpected ClientError should be re-raised."""
    mock_table = MagicMock()
    event = _make_event()

    error_response = {
        "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}
    }
    mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

    with pytest.raises(ClientError):
        check_in.check_in_user(event, mock_table)

    mock_table.update_item.assert_called_once()
