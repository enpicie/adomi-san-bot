import pytest
from unittest.mock import Mock, patch
import commands.setup.show_config_commands as show_config_commands

# Import necessary classes for type checking and mocking
from commands.models.response_message import ResponseMessage
from database.models.server_config import ServerConfig
from database.models.event_data import EventData

# Define mock classes for clear return values
class MockServerConfig(ServerConfig):
    def __init__(self, organizer_role="12345"):
        self.organizer_role = organizer_role

class MockEventData(EventData):
    def __init__(self, participant_role="67890"):
        self.participant_role = participant_role


# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object."""
    aws_services = Mock()
    aws_services.dynamodb_table = Mock() # Ensure dynamodb_table attribute exists
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a standard mock DiscordEvent object with base values."""
    event = Mock()
    event.get_server_id.return_value = "MOCK_SERVER_ID"
    return event

# --- Test Helpers for Patching ---

# These are the paths to the functions we need to mock
DB_GET_CONFIG_PATH = 'commands.setup.show_config_commands.db_helper.get_server_config_or_fail'
DB_GET_EVENT_DATA_PATH = 'commands.setup.show_config_commands.db_helper.get_server_event_data_or_fail'
MESSAGE_GET_PING_PATH = 'commands.setup.show_config_commands.message_helper.get_role_ping'

# --- Success Tests (Both roles present) ---

@patch(MESSAGE_GET_PING_PATH)
@patch(DB_GET_EVENT_DATA_PATH)
@patch(DB_GET_CONFIG_PATH)
def test_show_event_roles_success_both_roles(
    mock_get_config,
    mock_get_event_data,
    mock_get_role_ping,
    mock_discord_event,
    mock_aws_services
):
    """Tests successful retrieval and display when both roles are defined."""
    # Arrange
    MOCK_ORG_ROLE = "1000"
    MOCK_PART_ROLE = "2000"

    mock_get_config.return_value = MockServerConfig(organizer_role=MOCK_ORG_ROLE)
    mock_get_event_data.return_value = MockEventData(participant_role=MOCK_PART_ROLE)

    # Mock the role pinger to return predictable strings
    mock_get_role_ping.side_effect = lambda role_id: f"<@&{role_id}>"

    # Act
    response = show_config_commands.show_event_roles(mock_discord_event, mock_aws_services)

    # Assertions
    expected_content = (
        "**Event Roles:**\n"
        f"- Organizer: <@&{MOCK_ORG_ROLE}>\n"
        f"- Participant: <@&{MOCK_PART_ROLE}>"
    )
    assert response.content == expected_content
    assert response.allowed_mentions is not None
    mock_get_config.assert_called_once()
    mock_get_event_data.assert_called_once()
    assert mock_get_role_ping.call_count == 2


# --- Success Tests (Missing Participant Role) ---

@patch(MESSAGE_GET_PING_PATH)
@patch(DB_GET_EVENT_DATA_PATH)
@patch(DB_GET_CONFIG_PATH)
def test_show_event_roles_success_no_participant_role(
    mock_get_config,
    mock_get_event_data,
    mock_get_role_ping,
    mock_discord_event,
    mock_aws_services
):
    """Tests successful retrieval when only the organizer role is defined (participant_role is None)."""
    # Arrange
    MOCK_ORG_ROLE = "1000"
    mock_get_config.return_value = MockServerConfig(organizer_role=MOCK_ORG_ROLE)
    # Simulate missing/unset participant role
    mock_get_event_data.return_value = MockEventData(participant_role=None)

    # Mock the role pinger
    mock_get_role_ping.side_effect = lambda role_id: f"<@&{role_id}>"

    # Act
    response = show_config_commands.show_event_roles(mock_discord_event, mock_aws_services)

    # Assertions
    expected_content = (
        "**Event Roles:**\n"
        f"- Organizer: <@&{MOCK_ORG_ROLE}>\n"
        "- Participant: No Participant role set"
    )
    assert response.content == expected_content

    # Only the organizer role should have triggered the pinger
    assert mock_get_role_ping.call_count == 1
    mock_get_role_ping.assert_called_once_with(MOCK_ORG_ROLE)
    mock_get_config.assert_called_once()
    mock_get_event_data.assert_called_once()


# --- Failure Tests (Database Retrieval) ---

@patch(MESSAGE_GET_PING_PATH)
@patch(DB_GET_EVENT_DATA_PATH)
@patch(DB_GET_CONFIG_PATH)
def test_show_event_roles_fail_config(
    mock_get_config,
    mock_get_event_data,
    mock_get_role_ping,
    mock_discord_event,
    mock_aws_services
):
    """Tests failure path when retrieving Server Config fails."""
    # Arrange
    expected_response = ResponseMessage(content="Config Missing/Error")
    mock_get_config.return_value = expected_response # Failure on first DB call

    # Act
    response = show_config_commands.show_event_roles(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response
    mock_get_config.assert_called_once()
    mock_get_event_data.assert_not_called()
    mock_get_role_ping.assert_not_called()


@patch(MESSAGE_GET_PING_PATH)
@patch(DB_GET_EVENT_DATA_PATH)
@patch(DB_GET_CONFIG_PATH)
def test_show_event_roles_fail_event_data(
    mock_get_config,
    mock_get_event_data,
    mock_get_role_ping,
    mock_discord_event,
    mock_aws_services
):
    """Tests failure path when retrieving Event Data fails."""
    # Arrange
    expected_response = ResponseMessage(content="Event Data Missing/Error")
    mock_get_config.return_value = MockServerConfig() # First DB call succeeds
    mock_get_event_data.return_value = expected_response # Second DB call fails

    # Act
    response = show_config_commands.show_event_roles(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response
    mock_get_config.assert_called_once()
    mock_get_event_data.assert_called_once()
    mock_get_role_ping.assert_not_called()
