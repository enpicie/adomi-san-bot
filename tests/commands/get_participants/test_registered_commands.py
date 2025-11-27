import pytest
from typing import Optional
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError

import commands.get_registered.registered_commands as registered_commands
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.registered_participant import RegisteredParticipant

# --- Mock Classes ---

class MockServerConfig:
    """A minimal mock class that serves as a non-ResponseMessage return value."""
    def __init__(self, organizer_role="O_ROLE_ID"):
        self.organizer_role = organizer_role

class MockEventData:
    """Mock for EventData instance returned by db_helper.get_server_event_data_or_fail."""
    def __init__(self, checked_in: dict, registered: dict, participant_role: str = "P_ROLE_ID"):
        # The new command implementation only checks 'registered'
        self.checked_in = checked_in
        self.registered = registered
        self.participant_role = participant_role

# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object with a mock DynamoDB table and SQS queue."""
    mock_dynamodb_table = Mock()
    mock_sqs_queue = Mock()
    aws_services = Mock()
    aws_services.dynamodb_table = mock_dynamodb_table
    aws_services.remove_role_sqs_queue = mock_sqs_queue
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a mock DiscordEvent object with base values."""
    event = Mock()
    event.get_server_id.return_value = "S12345"
    return event

# --- Shared Patchers ---

@pytest.fixture(autouse=True)
def mock_external_modules():
    """Patch database.dynamodb_utils, permissions_helper, and message_helper.
       Module path updated to commands.get_registered.registered_commands."""
    with patch('commands.get_registered.registered_commands.db_helper') as mock_db, \
         patch('commands.get_registered.registered_commands.permissions_helper') as mock_perms, \
         patch('commands.get_registered.registered_commands.message_helper') as mock_msg_helper:

        mock_db.build_server_pk.return_value = "SERVER#S12345"
        mock_msg_helper.get_user_ping.side_effect = lambda user_id: f"<@{user_id}>"

        yield mock_db, mock_perms, mock_msg_helper

# ----------------------------------------------------
#  Tests for _verify_has_organizer_role
# ----------------------------------------------------

def test_verify_organizer_role_config_missing(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the server config is not found."""
    mock_db, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Config Missing")
    mock_db.get_server_config_or_fail.return_value = expected_response

    response = registered_commands._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_db.get_server_config_or_fail.assert_called_once()
    mock_external_modules[1].require_organizer_role.assert_not_called()


def test_verify_organizer_role_permission_missing(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the user lacks the organizer role."""
    mock_db, mock_perms, _ = mock_external_modules
    expected_response = ResponseMessage(content="Role Required")
    mock_db.get_server_config_or_fail.return_value = MockServerConfig()
    mock_perms.require_organizer_role.return_value = expected_response

    response = registered_commands._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_perms.require_organizer_role.assert_called_once()

def test_verify_organizer_role_success(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests success when config exists and user has the role."""
    mock_db, mock_perms, _ = mock_external_modules
    mock_db.get_server_config_or_fail.return_value = MockServerConfig()
    mock_perms.require_organizer_role.return_value = None # None means success

    response = registered_commands._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert response is None
    mock_perms.require_organizer_role.assert_called_once()

# ----------------------------------------------------
#  Tests for show_registered
# ----------------------------------------------------

# Patch the internal helper function for permission checks for public commands
@patch('commands.get_registered.registered_commands._verify_has_organizer_role', autospec=True)
def test_show_registered_permission_failure(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the user lacks the organizer role (checked by helper)."""
    expected_response = ResponseMessage(content="Permission Denied")
    mock_verify_role.return_value = expected_response

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_external_modules[0].get_server_event_data_or_fail.assert_not_called()

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_event_data_missing(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when server event data record is not found."""
    mock_db, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Event Data Missing")
    mock_db.get_server_event_data_or_fail.return_value = expected_response

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_no_registered_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests correct message when event data exists but 'registered' is empty."""
    mock_db, _, _ = mock_external_modules
    # Now explicitly checking for registered={}, not checked_in
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True}, registered={}
    )

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert "no registered users" in response.content

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_success_with_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful display of all registered users."""
    mock_db, _, mock_msg_helper = mock_external_modules # Unpack the message helper mock

    registered_users = {
        "U1": {RegisteredParticipant.Keys.USER_ID: "U1", RegisteredParticipant.Keys.DISPLAY_NAME: "User One"},
        "U2": {RegisteredParticipant.Keys.USER_ID: "U2", RegisteredParticipant.Keys.DISPLAY_NAME: "User Two"},
    }

    # Simulate two users registered
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={}, # Checked-in state doesn't matter for this command now
        registered=registered_users
    )

    # Mock the return value of the helper function
    expected_content = "✅ **Registered Users:**\n- <@U1>\n- <@U2>"
    mock_msg_helper.build_participants_list.return_value = expected_content

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    # Assert that the helper function was called correctly with the list of participant dictionaries
    mock_msg_helper.build_participants_list.assert_called_once_with(
        list_header="✅ **Registered Users:**",
        participants=list(registered_users.values())
    )

    # Assert the final response structure
    assert response.content == expected_content
    assert response.allowed_mentions is not None # Ensures with_silent_pings() was called

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_success_with_unlinked_user(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful display when a user is registered but discord ID is missing (placeholder)."""
    mock_db, _, mock_msg_helper = mock_external_modules # Unpack the message helper mock

    registered_users = {
        "U_GUEST": {
            RegisteredParticipant.Keys.USER_ID: RegisteredParticipant.DEFAULT_ID_PLACEHOLDER,
            RegisteredParticipant.Keys.DISPLAY_NAME: "Guest User"
        },
    }

    # Simulate a user with a placeholder ID
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={},
        registered=registered_users
    )

    # Mock the return value of the helper function, simulating the display name being used
    expected_content = "✅ **Registered Users:**\n- Guest User"
    mock_msg_helper.build_participants_list.return_value = expected_content

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    # Assert that the helper function was called correctly with the list of participant dictionaries
    mock_msg_helper.build_participants_list.assert_called_once_with(
        list_header="✅ **Registered Users:**",
        participants=list(registered_users.values())
    )

    # Assert the final response structure
    assert response.content == expected_content
    assert response.allowed_mentions is not None # Ensures with_silent_pings() was called

# ----------------------------------------------------
#  Tests for clear_registered
# ----------------------------------------------------

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', autospec=True)
def test_clear_registered_permission_failure(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the user lacks the organizer role."""
    expected_response = ResponseMessage(content="Permission Denied")
    mock_verify_role.return_value = expected_response

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_external_modules[0].get_server_event_data_or_fail.assert_not_called()

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_event_data_missing(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when server event data record is not found."""
    mock_db, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Event Data Missing")
    mock_db.get_server_event_data_or_fail.return_value = expected_response

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_no_registered_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests correct message when no users are registered."""
    mock_db, _, _ = mock_external_modules
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True}, registered={}
    )

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    assert "no registered users to clear" in response.content
    # Re-checking that dependencies are correct: `enqueue_remove_role_jobs` is NOT called here.
    # mock_external_modules[2].enqueue_remove_role_jobs.assert_not_called()
    mock_aws_services.dynamodb_table.update_item.assert_not_called()


@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_success(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful clearing of the registered map in DynamoDB."""
    mock_db, _, _ = mock_external_modules
    table = mock_aws_services.dynamodb_table
    PK = mock_db.build_server_pk.return_value

    # Event Data has registered users
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True, "U2": True}, # checked_in state doesn't matter
        registered={
            "U1": {RegisteredParticipant.Keys.USER_ID: "U1"},
            "U2": {RegisteredParticipant.Keys.USER_ID: "U2"}
        },
        participant_role="P_ROLE_ID" # role_id state doesn't matter
    )

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    # 1. Assert DynamoDB is updated to clear the 'registered' map
    table.update_item.assert_called_once()
    call_args = table.update_item.call_args[1]

    assert call_args["Key"] == {"PK": PK, "SK": EventData.Keys.SK_SERVER}
    assert call_args["UpdateExpression"] == f"SET {EventData.Keys.REGISTERED} = :empty_map"
    assert call_args["ExpressionAttributeValues"] == {":empty_map": {}}

    # 2. Assert success response matches the new command's output
    assert "All registered users have been cleared!" in response.content


@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_raises_on_client_error(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests that ClientError from DynamoDB is re-raised."""
    mock_db, _, _ = mock_external_modules
    table = mock_aws_services.dynamodb_table

    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={}, registered={"U1": {RegisteredParticipant.Keys.USER_ID: "U1"}}, participant_role="P_ROLE"
    )

    table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "DB is down"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        registered_commands.clear_registered(mock_discord_event, mock_aws_services)
