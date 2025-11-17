import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

import commands.check_in.check_in_commands as check_in
from commands.models.response_message import ResponseMessage
import utils.message_helper as msg_helper
import utils.discord_api_helper as discord_helper
import database.event_data_keys as event_data_keys
import database.models.participant as participant_module
import database.dynamodb_queries as db_helper
import constants


def _make_event():
    """Helper to build a mock DiscordEvent for reuse."""
    mock_event = MagicMock()
    mock_event.get_server_id.return_value = "123"
    mock_event.get_channel_id.return_value = "10"
    mock_event.get_user_id.return_value = "456"
    mock_event.get_username.return_value = "Alice"
    return mock_event


# ----------------------------------------------------
#  Successful check-in with participant role
# ----------------------------------------------------
def test_check_in_user_happy_path_with_role(monkeypatch):
    """Test a successful check-in where event data contains a participant_role."""
    mock_table = MagicMock()
    event = _make_event()

    role_id = "role123"

    # Mock dependencies
    monkeypatch.setattr(msg_helper, "get_user_ping", lambda uid: f"<@{uid}>")
    monkeypatch.setattr(db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

    # Return event_data containing a participant_role
    monkeypatch.setattr(db_helper, "get_server_event_data", lambda sid, table: {
        "participant_role": role_id
    })

    # Mock discord role assignment
    mock_add_role = MagicMock()
    monkeypatch.setattr(discord_helper, "add_role_to_user", mock_add_role)

    # Mock Participant.to_dict
    monkeypatch.setattr(participant_module.Participant, "to_dict", lambda self: {
        "user_id": self.user_id,
        "display_name": self.display_name
    })

    response = check_in.check_in_user(event, mock_table)

    # Check ResponseMessage
    assert isinstance(response, ResponseMessage)
    assert response.content == "✅ Checked in <@456>!"

    # Validate DynamoDB update call
    pk = "SERVER#123"
    sk = constants.SK_SERVER
    user_id = event.get_user_id()
    username = event.get_username()
    mock_table.update_item.assert_called_once()
    args, kwargs = mock_table.update_item.call_args
    assert kwargs["Key"] == {"PK": pk, "SK": sk}
    assert kwargs["ExpressionAttributeNames"] == {"#uid": user_id}
    assert kwargs["ExpressionAttributeValues"] == {
        ":participant_info": {"user_id": user_id, "display_name": username}
    }

    # Validate role assignment call
    mock_add_role.assert_called_once_with(
        guild_id=event.get_server_id(),
        user_id=event.get_user_id(),
        role_id=role_id
    )

