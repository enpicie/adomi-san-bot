import pytest
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError
from typing import Optional

# The module under test is assumed to be imported from your project root (src)
from commands.check_in import check_in_commands as target_module
from database.models.event_data import EventData
from database.models.participant import Participant
from commands.models.response_message import ResponseMessage
from database.models.participant import Participant # Needed for Keys

# --- Setup Fixtures (Shared Test Data) ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object."""
    mock_dynamodb_table = Mock()
    mock_sqs_queue = Mock()
    aws_services = Mock()
    aws_services.dynamodb_table = mock_dynamodb_table
    aws_services.remove_role_sqs_queue = mock_sqs_queue
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a standard mock DiscordEvent object."""
    event = Mock()
    event.get_server_id.return_value = "S12345"
    event.get_user_id.return_value = "U67890"
    event.get_username.return_value = "test_user"
    return event

# --- Tests for _verify_has_organizer_role (Helper Function) ---

# NOTE: Patching the modules where they are imported within the target_module
@patch('commands.check_in.check_in_commands.permissions_helper')
@patch('commands.check_in.check_in_commands.db_helper')
def test_verify_has_organizer_role_success(mock_db_helper, mock_permissions_helper, mock_discord_event, mock_aws_services):
    """Tests successful verification (returns None)."""
    mock_config = Mock()
    mock_db_helper.get_server_config_or_fail.return_value = mock_config
    mock_permissions_helper.require_organizer_role.return_value = None # Success case

    result = target_module._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert result is None
    mock_db_helper.get_server_config_or_fail.assert_called_once()
    mock_permissions_helper.require_organizer_role.assert_called_once_with(mock_config, mock_discord_event)

@patch('commands.check_in.check_in_commands.db_helper')
def test_verify_has_organizer_role_config_fail(mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests failure when server config is missing/error."""
    expected_response = ResponseMessage(content="Config Error")
    mock_db_helper.get_server_config_or_fail.return_value = expected_response

    result = target_module._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert result is expected_response
    mock_db_helper.get_server_config_or_fail.assert_called_once()

@patch('commands.check_in.check_in_commands.permissions_helper')
@patch('commands.check_in.check_in_commands.db_helper')
def test_verify_has_organizer_role_permission_fail(mock_db_helper, mock_permissions_helper, mock_discord_event, mock_aws_services):
    """Tests failure when user lacks organizer role."""
    mock_db_helper.get_server_config_or_fail.return_value = Mock()
    expected_response = ResponseMessage(content="Permission Error")
    mock_permissions_helper.require_organizer_role.return_value = expected_response

    result = target_module._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert result is expected_response
    mock_permissions_helper.require_organizer_role.assert_called_once()

# --- Tests for check_in_user ---

@patch('commands.check_in.check_in_commands.discord_helper')
@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands.db_helper')
def test_check_in_user_success_with_role(mock_db_helper, mock_message_helper, mock_discord_helper, mock_discord_event, mock_aws_services):
    """Tests successful check-in including role assignment."""
    # Setup mocks
    MOCK_ROLE_ID = "R99999"
    MOCK_USER_ID = mock_discord_event.get_user_id.return_value
    mock_event_data = Mock(participant_role=MOCK_ROLE_ID)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data
    # Mock the output of get_user_ping
    mock_message_helper.get_user_ping.return_value = f"<@{MOCK_USER_ID}>"

    # Execute
    response = target_module.check_in_user(mock_discord_event, mock_aws_services)

    # Assertions for success response
    assert response.content == f"✅ Checked in <@{MOCK_USER_ID}>!"

    # Assertions for DB update
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]

    # Check UpdateExpression parts
    assert call_args["Key"]["PK"] == mock_db_helper.build_server_pk(mock_discord_event.get_server_id.return_value)
    assert call_args["UpdateExpression"] == f"SET {EventData.Keys.CHECKED_IN}.#uid = :participant_info"
    assert call_args["ExpressionAttributeNames"] == {"#uid": MOCK_USER_ID}

    # Check that participant data was correctly formatted
    participant_data = call_args["ExpressionAttributeValues"][":participant_info"]
    assert participant_data[Participant.Keys.USER_ID] == MOCK_USER_ID
    assert participant_data[Participant.Keys.DISPLAY_NAME] == mock_discord_event.get_username.return_value

    # Assertions for role assignment
    mock_discord_helper.add_role_to_user.assert_called_once_with(
        guild_id=mock_discord_event.get_server_id.return_value,
        user_id=MOCK_USER_ID,
        role_id=MOCK_ROLE_ID
    )

@patch('commands.check_in.check_in_commands.discord_helper')
@patch('commands.check_in.check_in_commands.db_helper')
def test_check_in_user_success_no_role(mock_db_helper, mock_discord_helper, mock_discord_event, mock_aws_services):
    """Tests successful check-in without role assignment (participant_role is None)."""
    # Setup mocks
    mock_event_data = Mock(participant_role=None) # No role set
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    target_module.check_in_user(mock_discord_event, mock_aws_services)

    # Assertions for role assignment (should NOT be called)
    mock_discord_helper.add_role_to_user.assert_not_called()

@patch('commands.check_in.check_in_commands.db_helper')
def test_check_in_user_data_fail(mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests failure when event data is missing/error."""
    expected_response = ResponseMessage(content="Data Error")
    mock_db_helper.get_server_event_data_or_fail.return_value = expected_response

    result = target_module.check_in_user(mock_discord_event, mock_aws_services)

    assert result is expected_response
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

# --- Tests for show_checked_in ---

@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_checked_in_success(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """Tests successful retrieval and display of check-ins, using message_helper."""
    # Setup mocks
    mock_verify_role.return_value = None # Permission success

    # 1. Define checked_in map with required keys
    checked_in_map = {
        "U1": {Participant.Keys.USER_ID: "U1", Participant.Keys.DISPLAY_NAME: "Alice"},
        "U2": {Participant.Keys.USER_ID: "U2", Participant.Keys.DISPLAY_NAME: "Bob"}
    }
    mock_event_data = Mock(checked_in=checked_in_map)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # 2. Mock message_helper.get_user_ping to return the ping for display
    mock_message_helper.get_user_ping.side_effect = lambda user_id: f"<@{user_id}>"

    # Execute
    response = target_module.show_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    expected_content = (
        "✅ **Checked-in Users:**\n"
        "- <@U1>\n"
        "- <@U2>"
    )
    assert response.content == expected_content
    # Check that get_user_ping was called for both users
    mock_message_helper.get_user_ping.assert_has_calls([call("U1"), call("U2")], any_order=True)
    assert response.allowed_mentions is not None

@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_checked_in_empty(mock_db_helper, mock_verify_role, mock_discord_event, mock_aws_services):
    """Tests case where no users are checked in."""
    # Setup mocks
    mock_verify_role.return_value = None # Permission success
    mock_event_data = Mock(checked_in={})
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    response = target_module.show_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    assert response.content == "ℹ️ There are currently no checked-in users."

@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
def test_show_checked_in_permission_fail(mock_verify_role, mock_discord_event, mock_aws_services):
    """Tests failure when permission check fails."""
    expected_response = ResponseMessage(content="No Permission")
    mock_verify_role.return_value = expected_response

    result = target_module.show_checked_in(mock_discord_event, mock_aws_services)

    assert result is expected_response

# --- Tests for clear_checked_in ---

@patch('commands.check_in.check_in_commands.role_removal_queue')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_clear_checked_in_success_with_role(mock_db_helper, mock_verify_role, mock_role_removal_queue, mock_discord_event, mock_aws_services):
    """Tests successful clearing of check-ins and role removal queueing."""
    # Setup mocks
    mock_verify_role.return_value = None # Permission success
    MOCK_SERVER_ID = mock_discord_event.get_server_id.return_value
    MOCK_ROLE_ID = "R99999"
    checked_in_map = {
        "U1": {Participant.Keys.USER_ID: "U1", Participant.Keys.DISPLAY_NAME: "Alice"},
        "U2": {Participant.Keys.USER_ID: "U2", Participant.Keys.DISPLAY_NAME: "Bob"}
    }
    mock_event_data = Mock(checked_in=checked_in_map, participant_role=MOCK_ROLE_ID)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    response = target_module.clear_checked_in(mock_discord_event, mock_aws_services)

    # Assertions for success response
    assert response.content == "✅ All check-ins have been cleared, and I've queued up participant role removals 🫡"

    # Assertions for role removal queue
    mock_role_removal_queue.enqueue_remove_role_jobs.assert_called_once_with(
        server_id=MOCK_SERVER_ID,
        user_ids=["U1", "U2"], # keys of the map
        role_id=MOCK_ROLE_ID,
        sqs_queue=mock_aws_services.remove_role_sqs_queue
    )

    # Assertions for DB update (clearing the map)
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]
    assert call_args["UpdateExpression"] == "SET checked_in = :empty_map"
    assert call_args["ExpressionAttributeValues"] == {":empty_map": {}}

@patch('commands.check_in.check_in_commands.role_removal_queue')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_clear_checked_in_success_no_role(mock_db_helper, mock_verify_role, mock_role_removal_queue, mock_discord_event, mock_aws_services):
    """Tests successful clearing when no participant role is configured (DB update should NOT be called)."""
    # Setup mocks
    mock_verify_role.return_value = None
    checked_in_map = {"U1": {Participant.Keys.USER_ID: "U1", Participant.Keys.DISPLAY_NAME: "Alice"}}
    mock_event_data = Mock(checked_in=checked_in_map, participant_role=None) # No role
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    target_module.clear_checked_in(mock_discord_event, mock_aws_services)

    # Assertions for role removal queue (called even if role is None)
    mock_role_removal_queue.enqueue_remove_role_jobs.assert_called_once()

    # Assertions for DB update (should NOT clear the map if participant_role is None)
    # The code only updates the DB if participant_role is truthy.
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
def test_clear_checked_in_permission_fail(mock_verify_role, mock_discord_event, mock_aws_services):
    """Tests failure when permission check fails."""
    expected_response = ResponseMessage(content="No Permission")
    mock_verify_role.return_value = expected_response

    result = target_module.clear_checked_in(mock_discord_event, mock_aws_services)

    assert result is expected_response

@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_clear_checked_in_empty(mock_db_helper, mock_verify_role, mock_discord_event, mock_aws_services):
    """Tests case where no users are checked in to clear."""
    # Setup mocks
    mock_verify_role.return_value = None
    mock_event_data = Mock(checked_in={})
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    response = target_module.clear_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    assert response.content == "ℹ️ There are no checked-in users to clear."
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('commands.check_in.check_in_commands.role_removal_queue')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_clear_checked_in_dynamodb_error(mock_db_helper, mock_verify_role, mock_role_removal_queue, mock_discord_event, mock_aws_services):
    """Tests that ClientError is re-raised during clear_checked_in."""
    # Setup mocks
    mock_verify_role.return_value = None
    mock_event_data = Mock(checked_in={"U1": {Participant.Keys.USER_ID: "U1"}}, participant_role="R999")
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Simulate a ClientError on the DB update
    mock_aws_services.dynamodb_table.update_item.side_effect = ClientError({"Error": {"Code": "TestError"}}, "UpdateItem")

    # Execute and Assert
    with pytest.raises(ClientError):
        target_module.clear_checked_in(mock_discord_event, mock_aws_services)
