import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
import commands.get_registered.startgg.startgg_api as startgg_api
import commands.get_registered.startgg.startgg_commands as startgg_commands

# Imports for models and constants
import commands.get_registered.source_constants as source_constants
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.participant import Participant
from database.models.registered_participant import RegisteredParticipant
from aws_services import AWSServices # Needed for type hinting in fixture
from commands.models.discord_event import DiscordEvent # Needed for type hinting in fixture



# --- Mock StartggEvent Model (Copied from user's model file for internal testing) ---

@dataclass
class StartggEvent:
    tourney_name: str
    participants: List[RegisteredParticipant] = field(default_factory=list)
    no_discord_participants: List[Participant] = field(default_factory=list)

    # Simplified methods for testing purposes (real methods are in the user's model file)
    @classmethod
    def from_dict(cls, event_data: Dict[str, Any]) -> 'StartggEvent':
        raise NotImplementedError("Not needed for these tests")

    @staticmethod
    def _parse_participants(event_data: Dict[str, Any]) -> tuple[List[RegisteredParticipant], List[Participant]]:
        raise NotImplementedError("Not needed for these tests")

# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object with a mock DynamoDB table."""
    mock_dynamodb_table = Mock()
    aws_services = Mock(spec=AWSServices)
    aws_services.dynamodb_table = mock_dynamodb_table
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a standard mock DiscordEvent object with event_link input."""
    event = Mock(spec=DiscordEvent)
    event.get_server_id.return_value = "S12345"
    event.get_command_input_value.return_value = "https://www.start.gg/tournament/test/event/test-event"
    return event

# --- Mock Data Helpers ---

def create_mock_startgg_event(
    num_registered: int = 1,
    num_no_discord: int = 0,
    tourney_name: str = "Test Tournament"
) -> StartggEvent:
    """Creates a mock StartggEvent object for testing."""
    registered = []
    for i in range(num_registered):
        registered.append(RegisteredParticipant(
            display_name=f"User{i}",
            user_id=f"DiscordID{i}",
            source=source_constants.STARTGG,
            external_id=f"StartGGID{i}"
        ))

    no_discord = []
    for i in range(num_no_discord):
        no_discord.append(Participant(
            display_name=f"AnonUser{i}",
            user_id="no_id"
        ))

    return StartggEvent(
        tourney_name=tourney_name,
        participants=registered,
        no_discord_participants=no_discord
    )


# --- Test Cases ---

@patch('utils.permissions_helper.require_organizer_role')
def test_get_registered_startgg_permission_denied(mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests failure when user lacks the organizer role."""
    # Arrange
    expected_response = ResponseMessage(content="Permission Denied")
    mock_require_organizer_role.return_value = expected_response

    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert response is expected_response
    mock_require_organizer_role.assert_called_once_with(mock_discord_event)
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=False)
def test_get_registered_startgg_invalid_url(mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests failure when the provided start.gg URL is invalid."""
    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert response.content.startswith("😖 Sorry! This start.gg event link is not valid.")
    mock_is_valid_startgg_url.assert_called_once_with(mock_discord_event.get_command_input_value.return_value)
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=True)
@patch('commands.get_registered.startgg.startgg_api.query_startgg_event')
def test_get_registered_startgg_no_participants_found(mock_query_startgg_event, mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests the response when no participants (registered or anonymous) are found."""
    # Arrange
    mock_query_startgg_event.return_value = create_mock_startgg_event(num_registered=0, num_no_discord=0)

    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert "😔 No registered participants found for this start.gg event" == response.content
    mock_query_startgg_event.assert_called_once()
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=True)
@patch('commands.get_registered.startgg.startgg_api.query_startgg_event')
@patch('database.dynamodb_utils.build_server_pk', return_value="SERVER#S12345")
def test_get_registered_startgg_success_registered_only(mock_build_server_pk, mock_query_startgg_event, mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests successful retrieval and update when only Discord-linked participants are found."""
    # Arrange
    mock_query_startgg_event.return_value = create_mock_startgg_event(num_registered=3, num_no_discord=0)

    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert "👍 Found 3 participants registered in start.gg!" in response.content

    # Assert DynamoDB update
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]

    # Check Key
    assert call_args["Key"] == {
        "PK": "SERVER#S12345",
        "SK": EventData.Keys.SK_SERVER
    }
    # Check Value content (structure verification)
    registered_data = call_args["ExpressionAttributeValues"][":startgg_registered"]
    assert len(registered_data) == 3
    assert registered_data["DiscordID0"]["display_name"] == "User0"
    assert "DiscordID2" in registered_data


@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=True)
@patch('commands.get_registered.startgg.startgg_api.query_startgg_event')
def test_get_registered_startgg_success_no_discord_only(mock_query_startgg_event, mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests successful retrieval when only participants without Discord links are found (no DB update)."""
    # Arrange
    mock_query_startgg_event.return_value = create_mock_startgg_event(num_registered=0, num_no_discord=2)

    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert "👍 Found 0 participants registered in start.gg!" in response.content
    assert "**I found these start.gg users do not have Discord linked**" in response.content
    assert "* AnonUser0" in response.content
    assert "* AnonUser1" in response.content

    # Assert DynamoDB update (should not be called because startgg_event.participants is empty)
    mock_aws_services.dynamodb_table.update_item.assert_not_called()

@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=True)
@patch('commands.get_registered.startgg.startgg_api.query_startgg_event')
@patch('database.dynamodb_utils.build_server_pk', return_value="SERVER#S12345")
def test_get_registered_startgg_success_mixed(mock_build_server_pk, mock_query_startgg_event, mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests successful retrieval with a mix of registered (2) and no-discord (1) participants (DB update and report)."""
    # Arrange
    mock_query_startgg_event.return_value = create_mock_startgg_event(num_registered=2, num_no_discord=1)

    # Act
    response = startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)

    # Assert
    assert "👍 Found 2 participants registered in start.gg!" in response.content
    assert "**I found these start.gg users do not have Discord linked**" in response.content
    assert "* AnonUser0" in response.content # Only one anon user

    # Assert DynamoDB update (should be called for the 2 registered participants)
    mock_aws_services.dynamodb_table.update_item.assert_called_once()
    call_args = mock_aws_services.dynamodb_table.update_item.call_args[1]
    registered_data = call_args["ExpressionAttributeValues"][":startgg_registered"]
    assert len(registered_data) == 2


@patch('utils.permissions_helper.require_organizer_role', return_value=None)
@patch('commands.get_registered.startgg.startgg_api.is_valid_startgg_url', return_value=True)
@patch('commands.get_registered.startgg.startgg_api.query_startgg_event')
@patch('database.dynamodb_utils.build_server_pk', return_value="SERVER#S12345")
def test_get_registered_startgg_dynamodb_error(mock_build_server_pk, mock_query_startgg_event, mock_is_valid_startgg_url, mock_require_organizer_role, mock_discord_event, mock_aws_services):
    """Tests that a ClientError from DynamoDB is re-raised."""
    # Arrange
    mock_query_startgg_event.return_value = create_mock_startgg_event(num_registered=1)

    # Simulate DB error by raising ClientError on update
    mock_aws_services.dynamodb_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "DB is down"}},
        "UpdateItem"
    )

    # Act / Assert
    with pytest.raises(ClientError):
        startgg_commands.get_registered_startgg(mock_discord_event, mock_aws_services)
