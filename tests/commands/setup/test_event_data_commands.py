import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

import commands.setup.event_data_commands as event_data_commands

# Import necessary classes for type checking and mocking
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData

# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object."""
    mock_dynamodb_table = Mock()
    aws_services = Mock()
    aws_services.dynamodb_table = mock_dynamodb_table
    # The queue is not used in this specific function but good to include for a full AWSServices mock
    aws_services.remove_role_sqs_queue = Mock()
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a standard mock DiscordEvent object with base values."""
    event = Mock()
    event.get_server_id.return_value = "S12345"
    # Default inputs for success path (setting a role)
    event.get_command_input_value.side_effect = lambda key: (
        "Role456" if key == "participant_role" else False
    )
    return event

# --- Permission Failure Tests ---

@patch('commands.setup.event_data_commands.permissions_helper')
def test_set_participant_role_insufficient_permissions(mock_permissions_helper, mock_discord_event, mock_aws_services):
    """Tests failure when user lacks 'manage_server' permission."""
    expected_response = ResponseMessage(content="Permission Denied")
    mock_permissions_helper.require_manage_server_permission.return_value = expected_response

    response = event_data_commands.set_participant_role(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response
    mock_permissions_helper.require_manage_server_permission.assert_called_once_with(mock_discord_event)
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

# --- Config/Database Pre-Check Failure Tests ---

@patch('commands.setup.event_data_commands.db_helper')
@patch('commands.setup.event_data_commands.permissions_helper')
def test_set_participant_role_config_check_failure(mock_permissions_helper, mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests failure when the server config is not found/fails to load."""
    # Setup mocks
    mock_permissions_helper.require_manage_server_permission.return_value = None # Permission success
    expected_response = ResponseMessage(content="Config Missing/Error")
    mock_db_helper.get_server_config_or_fail.return_value = expected_response

    response = event_data_commands.set_participant_role(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response
    mock_db_helper.get_server_config_or_fail.assert_called_once()
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

# --- Success Tests (Setting/Updating Role) ---

@patch('commands.setup.event_data_commands.db_helper')
@patch('commands.setup.event_data_commands.permissions_helper')
def test_set_participant_role_success_set(mock_permissions_helper, mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests successfully setting a new participant role ID."""
    MOCK_ROLE_ID = "Role456"
    MOCK_SERVER_ID = mock_discord_event.get_server_id.return_value

    # Setup mocks
    mock_permissions_helper.require_manage_server_permission.return_value = None # Permission success
    mock_db_helper.get_server_config_or_fail.return_value = Mock() # Config success (return value doesn't matter here)
    mock_db_helper.build_server_pk.return_value = f"SERVER#{MOCK_SERVER_ID}"
    # Input is set by fixture: "Role456"

    # Execute
    response = event_data_commands.set_participant_role(mock_discord_event, mock_aws_services)

    # Assertions for DynamoDB update
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]

    # Check Key
    assert call_args["Key"] == {
        "PK": f"SERVER#{MOCK_SERVER_ID}",
        "SK": EventData.Keys.SK_SERVER # Assuming server-wide configuration
    }
    # Check Update Expression
    assert call_args["UpdateExpression"] == f"SET {EventData.Keys.PARTICIPANT_ROLE} = :r"
    # Check Value
    assert call_args["ExpressionAttributeValues"] == {":r": MOCK_ROLE_ID}

    # Assertions for response message
    assert "updated successfully" in response.content
    assert response.content.startswith("👍")

# --- Success Tests (Removing Role) ---

@patch('commands.setup.event_data_commands.db_helper')
@patch('commands.setup.event_data_commands.permissions_helper')
def test_set_participant_role_success_remove(mock_permissions_helper, mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests successfully removing the participant role using the 'remove_role' flag."""
    MOCK_SERVER_ID = mock_discord_event.get_server_id.return_value

    # Setup mocks
    mock_permissions_helper.require_manage_server_permission.return_value = None
    mock_db_helper.get_server_config_or_fail.return_value = Mock()
    mock_db_helper.build_server_pk.return_value = f"SERVER#{MOCK_SERVER_ID}"

    # Simulate user input: remove_role=True
    mock_discord_event.get_command_input_value.side_effect = lambda key: (
        True if key == "remove_role" else "Role456" # The 'participant_role' value is irrelevant
    )

    # Execute
    response = event_data_commands.set_participant_role(mock_discord_event, mock_aws_services)

    # Assertions for DynamoDB update
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]

    # Check that the role value is explicitly set to "" (empty string for removal)
    assert call_args["ExpressionAttributeValues"] == {":r": ""}

    # Assertions for response message
    assert "removed successfully" in response.content
    assert response.content.startswith("👍")

# --- Exception Tests ---

@patch('commands.setup.event_data_commands.db_helper')
@patch('commands.setup.event_data_commands.permissions_helper')
def test_set_participant_role_raises_on_client_error(mock_permissions_helper, mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests that ClientError from DynamoDB is re-raised."""
    # Setup mocks
    mock_permissions_helper.require_manage_server_permission.return_value = None
    mock_db_helper.get_server_config_or_fail.return_value = Mock()

    # Simulate DB error
    mock_aws_services.dynamodb_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "DB is down"}},
        "UpdateItem"
    )

    # Execute and Assert
    with pytest.raises(ClientError):
        event_data_commands.set_participant_role(mock_discord_event, mock_aws_services)
