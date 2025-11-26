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
    """Patch database.dynamodb_utils, permissions_helper, role_removal_queue, and message_helper."""
    with patch('commands.get_registered.registered_commands.db_helper') as mock_db, \
         patch('commands.get_registered.registered_commands.permissions_helper') as mock_perms, \
         patch('commands.get_registered.registered_commands.role_removal_queue') as mock_removal_queue, \
         patch('commands.get_registered.registered_commands.message_helper') as mock_msg_helper:

        mock_db.build_server_pk.return_value = "SERVER#S12345"
        mock_msg_helper.get_user_ping.side_effect = lambda user_id: f"<@{user_id}>"

        yield mock_db, mock_perms, mock_removal_queue, mock_msg_helper

# ----------------------------------------------------
#  Tests for _verify_has_organizer_role
# ----------------------------------------------------

def test_verify_organizer_role_config_missing(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the server config is not found."""
    mock_db, _, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Config Missing")
    mock_db.get_server_config_or_fail.return_value = expected_response

    response = registered_commands._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_db.get_server_config_or_fail.assert_called_once()
    mock_external_modules[1].require_organizer_role.assert_not_called()


def test_verify_organizer_role_permission_missing(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests failure when the user lacks the organizer role."""
    mock_db, mock_perms, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Role Required")
    mock_db.get_server_config_or_fail.return_value = MockServerConfig()
    mock_perms.require_organizer_role.return_value = expected_response

    response = registered_commands._verify_has_organizer_role(mock_discord_event, mock_aws_services)

    assert response is expected_response
    mock_perms.require_organizer_role.assert_called_once()

def test_verify_organizer_role_success(mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests success when config exists and user has the role."""
    mock_db, mock_perms, _, _ = mock_external_modules
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
    mock_db, _, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Event Data Missing")
    mock_db.get_server_event_data_or_fail.return_value = expected_response

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_no_checked_in_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests correct message when event data exists but checked_in is empty."""
    mock_db, _, _, _ = mock_external_modules
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={}, registered={}
    )

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert "no checked-in users" in response.content

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_success_with_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful display of checked-in users."""
    mock_db, _, _, _ = mock_external_modules

    # Simulate two users checked in
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True, "U2": True},
        registered={
            "U1": {RegisteredParticipant.Keys.USER_ID: "U1", RegisteredParticipant.Keys.DISPLAY_NAME: "User One"},
            "U2": {RegisteredParticipant.Keys.USER_ID: "U2", RegisteredParticipant.Keys.DISPLAY_NAME: "User Two"},
        }
    )

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert "Registered Users" in response.content
    assert "- <@U1>" in response.content
    assert "- <@U2>" in response.content
    assert response.allowed_mentions is not None

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_show_registered_success_with_unlinked_user(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful display when a user is registered but discord ID is missing."""
    mock_db, _, _, _ = mock_external_modules

    # Simulate a user with no discord ID (NO_DISCORD_ID_IDENTIFIER)
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U_GUEST": True},
        registered={
            "U_GUEST": {
                RegisteredParticipant.Keys.USER_ID: RegisteredParticipant.NO_DISCORD_ID_IDENTIFIER,
                RegisteredParticipant.Keys.DISPLAY_NAME: "Guest User"
            },
        }
    )

    response = registered_commands.show_registered(mock_discord_event, mock_aws_services)

    assert "Registered Users" in response.content
    # Should use the display name since user_id is the NO_DISCORD_ID_IDENTIFIER
    assert "- Guest User" in response.content
    assert "<@" not in response.content # No ping should be generated

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
    mock_db, _, _, _ = mock_external_modules
    expected_response = ResponseMessage(content="Event Data Missing")
    mock_db.get_server_event_data_or_fail.return_value = expected_response

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    assert response is expected_response

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_no_checked_in_users(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests correct message when no users are checked in."""
    mock_db, _, _, _ = mock_external_modules
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={}, registered={}
    )

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    assert "no checked-in users to clear" in response.content
    mock_external_modules[2].enqueue_remove_role_jobs.assert_not_called()


@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_success_with_participant_role(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful clearing when a participant role is configured."""
    mock_db, _, mock_removal_queue, _ = mock_external_modules
    table = mock_aws_services.dynamodb_table
    sqs_queue = mock_aws_services.remove_role_sqs_queue
    PK = mock_db.build_server_pk.return_value

    CHECKED_IN_USERS = ["U1", "U2"]
    PARTICIPANT_ROLE_ID = "P_ROLE_ID"

    # Event Data has checked in users and a participant role ID
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True, "U2": True},
        registered={},
        participant_role=PARTICIPANT_ROLE_ID
    )

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    # 1. Assert role removal jobs are queued
    mock_removal_queue.enqueue_remove_role_jobs.assert_called_once_with(
        server_id=mock_discord_event.get_server_id.return_value,
        user_ids=CHECKED_IN_USERS,
        role_id=PARTICIPANT_ROLE_ID,
        sqs_queue=sqs_queue
    )

    # 2. Assert DynamoDB is updated to clear the checked_in map
    table.update_item.assert_called_once()
    call_args = table.update_item.call_args[1]

    assert call_args["Key"] == {"PK": PK, "SK": EventData.Keys.SK_SERVER}
    assert call_args["UpdateExpression"] == "SET checked_in = :empty_map"
    assert call_args["ExpressionAttributeValues"] == {":empty_map": {}}

    # 3. Assert success response
    assert "check-ins have been cleared" in response.content


@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_success_no_participant_role(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests successful clearing when NO participant role is configured (DB update is skipped)."""
    mock_db, _, mock_removal_queue, _ = mock_external_modules
    table = mock_aws_services.dynamodb_table
    sqs_queue = mock_aws_services.remove_role_sqs_queue

    CHECKED_IN_USERS = ["U1"]
    PARTICIPANT_ROLE_ID = "" # Empty role ID (falsy)

    # Event Data has checked in users but no participant role
    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True},
        registered={},
        participant_role=PARTICIPANT_ROLE_ID
    )

    response = registered_commands.clear_registered(mock_discord_event, mock_aws_services)

    # 1. Assert role removal jobs are still queued (it is up to the queue worker to handle the empty role_id)
    mock_removal_queue.enqueue_remove_role_jobs.assert_called_once_with(
        server_id=mock_discord_event.get_server_id.return_value,
        user_ids=CHECKED_IN_USERS,
        role_id=PARTICIPANT_ROLE_ID,
        sqs_queue=sqs_queue
    )

    # 2. Assert DynamoDB update is NOT called because participant_role is falsy ("")
    table.update_item.assert_not_called()

    # 3. Assert success response
    assert "check-ins have been cleared" in response.content

@patch('commands.get_registered.registered_commands._verify_has_organizer_role', return_value=None)
def test_clear_registered_raises_on_client_error(mock_verify_role, mock_external_modules, mock_discord_event, mock_aws_services):
    """Tests that ClientError from DynamoDB is re-raised."""
    mock_db, _, _, _ = mock_external_modules
    table = mock_aws_services.dynamodb_table

    mock_db.get_server_event_data_or_fail.return_value = MockEventData(
        checked_in={"U1": True}, registered={}, participant_role="P_ROLE"
    )

    table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "DB is down"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        registered_commands.clear_registered(mock_discord_event, mock_aws_services)
