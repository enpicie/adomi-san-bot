import pytest
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError

import commands.setup.server_config_commands as server_config_commands

# Import necessary classes for key access and type checking
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.server_config import ServerConfig
from enums import EventMode

class MockServerConfig:
    """A minimal mock class that serves as an instance of ServerConfig for testing instance checks."""
    def __init__(self, pk="SERVER#S12345", sk="CONFIG"):
        self.pk = pk
        self.sk = sk
        # Add keys as properties if needed for detailed checks, but usually not required for simple instance checks
        pass

# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object with a mock DynamoDB table."""
    mock_dynamodb_table = Mock()
    aws_services = Mock()
    aws_services.dynamodb_table = mock_dynamodb_table
    aws_services.remove_role_sqs_queue = Mock() # Included for completeness
    return aws_services

@pytest.fixture
def mock_discord_event_setup():
    """Fixture for a mock DiscordEvent object with base values and setup-specific inputs."""
    event = Mock()
    event.get_server_id.return_value = "S12345"
    # Default input for organizer_role in setup_server/set_organizer_role tests
    event.get_command_input_value.side_effect = lambda key: (
        "OrganizerRoleID" if key == "organizer_role" else
        "ParticipantRoleID" if key == "participant_role" else
        False # Default for remove_role
    )
    return event

# --- Permissions/DB Helper Shared Patchers ---

@pytest.fixture(autouse=True)
def mock_db_and_perms():
    """Patch database.dynamodb_utils and utils.permissions_helper for all tests."""
    # Use the full path for patching modules used within the target module
    with patch('commands.setup.server_config_commands.db_helper') as mock_db, \
         patch('commands.setup.server_config_commands.permissions_helper') as mock_perms:
        # Mock common functions used by multiple commands
        mock_db.build_server_pk.return_value = "SERVER#S12345"
        mock_perms.require_manage_server_permission.return_value = None # Assume success unless explicitly overridden
        yield mock_db, mock_perms

# ----------------------------------------------------
#  Tests for setup_server
# ----------------------------------------------------

def test_setup_server_insufficient_permissions(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests that setup_server fails if user lacks 'manage_server' permission."""
    _, mock_perms = mock_db_and_perms
    expected_response = ResponseMessage(content="Permission Denied")
    mock_perms.require_manage_server_permission.return_value = expected_response

    response = server_config_commands.setup_server(mock_discord_event_setup, mock_aws_services)

    assert response is expected_response
    mock_aws_services.dynamodb_table.put_item.assert_not_called()

def test_setup_server_already_set_up(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """
    Tests that setup_server returns a message if server configuration already exists.
    This is checked via db_helper.get_server_config_or_fail returning a non-ResponseMessage object.
    """
    mock_db, _ = mock_db_and_perms

    # Mock db_helper to return a ServerConfig instance (already exists)
    mock_db.get_server_config_or_fail.return_value = MockServerConfig()

    response = server_config_commands.setup_server(mock_discord_event_setup, mock_aws_services)

    assert isinstance(response, ResponseMessage)
    assert "already set up" in response.content
    mock_aws_services.dynamodb_table.put_item.assert_not_called()

def test_setup_server_success_server_wide_mode(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """
    Tests successful setup, ensuring both CONFIG and SERVER records are created without
    ConditionExpression, as per the updated command implementation.
    """
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table
    PK = mock_db.build_server_pk.return_value

    # Mock db_helper to return ResponseMessage (config not found/fail), allowing setup to proceed
    mock_db.get_server_config_or_fail.return_value = ResponseMessage(content="Config Not Found")

    response = server_config_commands.setup_server(mock_discord_event_setup, mock_aws_services)

    # Assertions for response
    assert isinstance(response, ResponseMessage)
    assert f"Server setup complete with event mode `{EventMode.SERVER_WIDE.value}`." in response.content

    # Assertions for DynamoDB calls (2 put_item calls)
    assert table.put_item.call_count == 2

    # 1. Check CONFIG record creation (Call 1)
    config_call = table.put_item.call_args_list[0]
    assert config_call.kwargs["Item"] == {
        "PK": PK,
        "SK": ServerConfig.Keys.SK_CONFIG,
        ServerConfig.Keys.EVENT_MODE: EventMode.SERVER_WIDE.value,
        ServerConfig.Keys.ORGANIZER_ROLE: "OrganizerRoleID"
    }
    # IMPORTANT FIX: ConditionExpression should NOT be present now
    assert "ConditionExpression" not in config_call.kwargs

    # 2. Check Event Data record creation (Call 2)
    event_data_call = table.put_item.call_args_list[1]
    assert event_data_call.kwargs["Item"] == {
        "PK": PK,
        "SK": EventData.Keys.SK_SERVER,
        EventData.Keys.CHECKED_IN: {},
        EventData.Keys.REGISTERED: {},
        EventData.Keys.QUEUE: {}
    }
    # IMPORTANT FIX: ConditionExpression should NOT be present now
    assert "ConditionExpression" not in event_data_call.kwargs

def test_setup_server_raises_on_generic_client_error(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests that any other ClientError is re-raised."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table

    mock_db.get_server_config_or_fail.return_value = ResponseMessage(content="Config Not Found")

    # Simulate a generic ClientError
    table.put_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Boom"}},
        "PutItem"
    )

    with pytest.raises(ClientError):
        server_config_commands.setup_server(mock_discord_event_setup, mock_aws_services)


# ----------------------------------------------------
#  Tests for set_organizer_role
# ----------------------------------------------------

def test_set_organizer_role_insufficient_permissions(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests failure when user lacks 'manage_server' permission."""
    _, mock_perms = mock_db_and_perms
    expected_response = ResponseMessage(content="Permission Denied")
    mock_perms.require_manage_server_permission.return_value = expected_response

    response = server_config_commands.set_organizer_role(mock_discord_event_setup, mock_aws_services)

    assert response is expected_response
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

def test_set_organizer_role_config_check_failure(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests failure when server configuration record is not found."""
    mock_db, _ = mock_db_and_perms
    expected_response = ResponseMessage(content="Config Missing")
    mock_db.get_server_config_or_fail.return_value = expected_response

    response = server_config_commands.set_organizer_role(mock_discord_event_setup, mock_aws_services)

    assert response is expected_response
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

def test_set_organizer_role_success_update(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests successfully updating the organizer role ID."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table
    PK = mock_db.build_server_pk.return_value
    MOCK_ROLE_ID = "OrganizerRoleID"

    mock_db.get_server_config_or_fail.return_value = MockServerConfig() # Config exists

    response = server_config_commands.set_organizer_role(mock_discord_event_setup, mock_aws_services)

    # Assertions for DynamoDB update
    table.update_item.assert_called_once()
    call_args = table.update_item.call_args[1]

    assert call_args["Key"] == {"PK": PK, "SK": ServerConfig.Keys.SK_CONFIG}
    assert call_args["UpdateExpression"] == f"SET {ServerConfig.Keys.ORGANIZER_ROLE} = :r"
    assert call_args["ExpressionAttributeValues"] == {":r": MOCK_ROLE_ID}

    # Assertions for response message
    assert "Organizer role updated successfully" in response.content
    assert response.content.startswith("👍")

def test_set_organizer_role_raises_on_client_error(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests that ClientError from DynamoDB is re-raised."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table

    mock_db.get_server_config_or_fail.return_value = MockServerConfig()

    table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        server_config_commands.set_organizer_role(mock_discord_event_setup, mock_aws_services)

# ----------------------------------------------------
#  Tests for set_participant_role (Updated from previous request)
# ----------------------------------------------------

def test_set_participant_role_insufficient_permissions(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests failure when user lacks 'manage_server' permission."""
    _, mock_perms = mock_db_and_perms
    expected_response = ResponseMessage(content="Permission Denied")
    mock_perms.require_manage_server_permission.return_value = expected_response

    response = server_config_commands.set_participant_role(mock_discord_event_setup, mock_aws_services)

    assert response is expected_response
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

def test_set_participant_role_success_set(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests successfully setting a new participant role ID."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table
    PK = mock_db.build_server_pk.return_value
    MOCK_ROLE_ID = "ParticipantRoleID"

    mock_db.get_server_config_or_fail.return_value = MockServerConfig()

    # Ensure no removal flag is set
    mock_discord_event_setup.get_command_input_value.side_effect = lambda key: (
        MOCK_ROLE_ID if key == "participant_role" else
        False if key == "remove_role" else
        None
    )

    response = server_config_commands.set_participant_role(mock_discord_event_setup, mock_aws_services)

    # Assertions for DynamoDB update
    table.update_item.assert_called_once()
    call_args = table.update_item.call_args[1]

    # Check Key
    assert call_args["Key"] == {"PK": PK, "SK": EventData.Keys.SK_SERVER}
    # Check Update Expression
    assert call_args["UpdateExpression"] == f"SET {EventData.Keys.PARTICIPANT_ROLE} = :r"
    # Check Value
    assert call_args["ExpressionAttributeValues"] == {":r": MOCK_ROLE_ID}

    # Assertions for response message
    assert "updated successfully" in response.content

def test_set_participant_role_success_remove(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests successfully removing the participant role using the 'remove_role' flag."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table
    PK = mock_db.build_server_pk.return_value

    mock_db.get_server_config_or_fail.return_value = MockServerConfig()

    # Simulate user input: remove_role=True
    mock_discord_event_setup.get_command_input_value.side_effect = lambda key: (
        True if key == "remove_role" else
        "OldRoleID" # The 'participant_role' value is irrelevant when remove_role is True
    )

    response = server_config_commands.set_participant_role(mock_discord_event_setup, mock_aws_services)

    # Assertions for DynamoDB update
    table.update_item.assert_called_once()
    call_args = table.update_item.call_args[1]

    # Check that the role value is explicitly set to "" (empty string for removal)
    assert call_args["ExpressionAttributeValues"] == {":r": ""}

    # Assertions for response message
    assert "removed successfully" in response.content

def test_set_participant_role_config_check_failure(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests failure when the server config is not found/fails to load."""
    mock_db, _ = mock_db_and_perms
    expected_response = ResponseMessage(content="Config Missing/Error")
    mock_db.get_server_config_or_fail.return_value = expected_response

    response = server_config_commands.set_participant_role(mock_discord_event_setup, mock_aws_services)

    assert response is expected_response
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

def test_set_participant_role_raises_on_client_error(mock_db_and_perms, mock_discord_event_setup, mock_aws_services):
    """Tests that ClientError from DynamoDB is re-raised."""
    mock_db, _ = mock_db_and_perms
    table = mock_aws_services.dynamodb_table

    mock_db.get_server_config_or_fail.return_value = MockServerConfig()

    table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "DB is down"}},
        "UpdateItem"
    )

    with pytest.raises(ClientError):
        server_config_commands.set_participant_role(mock_discord_event_setup, mock_aws_services)
