import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from commands.check_in import check_in
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
import utils.message_helper as msg_helper


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    event_body = {
        "member": {
            "user": {
                "id": "123",
                "username": "Alice"
            }
        },
        "guild_id": "1",
        "channel_id": "10"
    }
    return DiscordEvent(event_body)


def test_check_in_user_calls_update_item(monkeypatch):
    """Test successful check-in calls update_item correctly and returns expected message."""
    # Mock the message helper to return a deterministic user ping
    monkeypatch.setattr(msg_helper, "get_user_ping", lambda uid: f"<@{uid}>")

    mock_table = MagicMock()
    event = _make_event()

    # Call the function
    response = check_in.check_in_user(event, mock_table)

    # Assertions
    assert isinstance(response, ResponseMessage)
    expected_message = f"Checked in <@{event.get_user_id()}>!"
    assert response.content == expected_message

    # Verify update_item was called with correct keys and attributes
    pk = f"SERVER#{event.get_server_id()}"
    sk = f"CHANNEL#{event.get_channel_id()}"
    user_id = event.get_user_id()
    username = event.get_username()

    mock_table.update_item.assert_called_once_with(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET checked_in.#uid = :user_info",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":user_info": {"username": username}},
        ConditionExpression="attribute_exists(PK)"
    )


def test_check_in_user_conditional_check_failed(monkeypatch):
    """Test case where DynamoDB record does not exist (ConditionalCheckFailedException)."""
    mock_table = MagicMock()
    event = _make_event()

    # Simulate ConditionalCheckFailedException
    error_response = {
        "Error": {"Code": "ConditionalCheckFailedException", "Message": "Record does not exist"}
    }
    mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

    response = check_in.check_in_user(event, mock_table)

    assert isinstance(response, ResponseMessage)
    expected_message = f"This channel has not been registered yet. Cannot check in {event.get_username()}."
    assert response.content == expected_message

    mock_table.update_item.assert_called_once()


def test_check_in_user_unexpected_client_error():
    """Test case where an unexpected ClientError is raised."""
    mock_table = MagicMock()
    event = _make_event()

    # Simulate unexpected ClientError (e.g., throttling)
    error_response = {
        "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}
    }
    mock_table.update_item.side_effect = ClientError(error_response, "UpdateItem")

    with pytest.raises(ClientError):
        check_in.check_in_user(event, mock_table)

    mock_table.update_item.assert_called_once()
