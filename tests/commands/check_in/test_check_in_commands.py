import pytest
from unittest.mock import Mock, patch

import commands.check_in.check_in_commands as check_in_commands

# Import necessary classes for type checking and mocking
from commands.models.response_message import ResponseMessage

# Define mock EventData class for consistent testing
class MockEventData:
    def __init__(self, registered, checked_in):
        self.registered = registered
        self.checked_in = checked_in

# Define constant paths for patching
COMMAND_MODULE = 'commands.check_in.check_in_commands'
DB_HELPER_PATH = f'{COMMAND_MODULE}.db_helper'
MESSAGE_HELPER_PATH = f'{COMMAND_MODULE}.message_helper'

# --- Fixtures ---

@pytest.fixture
def mock_aws_services():
    """Fixture for a standard mock AWSServices object."""
    aws_services = Mock()
    aws_services.dynamodb_table = Mock()
    return aws_services

@pytest.fixture
def mock_discord_event():
    """Fixture for a standard mock DiscordEvent object with base values."""
    event = Mock()
    event.get_server_id.return_value = "S12345"
    # Default inputs for success path (no ping)
    event.get_command_input_value.side_effect = lambda key: (
        True if key == "ping_users" else False
    )
    return event

# --- Success Tests ---

@patch(f'{COMMAND_MODULE}.message_helper.build_participants_list') # New Patch
@patch(f'{COMMAND_MODULE}._verify_has_organizer_role', return_value=None)
@patch(f'{DB_HELPER_PATH}.get_server_event_data_or_fail')
def test_show_not_checked_in_success_both_lists_present(
    mock_get_event_data,
    mock_verify_role,
    mock_build_list, # The mock is now injected here
    mock_discord_event,
    mock_aws_services
):
    """Tests when both the 'not checked in' and 'not registered' lists have participants."""
    # Arrange
    MOCK_EVENT_DATA = MockEventData(
        registered={'u1': 'UserA', 'u2': 'UserB'},
        checked_in={'u2': 'UserB', 'u3': 'UserC'}
    )
    mock_get_event_data.return_value = MOCK_EVENT_DATA

    # Configure the mock's side effect directly here
    mock_build_list.side_effect = lambda list_header, participants: f"--- {list_header} ({len(participants)} users) ---"

    # Act
    response = check_in_commands.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    # 1. Check DB and Role checks
    mock_verify_role.assert_called_once()
    mock_get_event_data.assert_called_once()

    # 2. Check build_participants_list calls
    # Not Checked In: u1 (1 user)
    mock_build_list.assert_any_call(list_header="🔍 **Participants not yet checked-in:**", participants=['UserA'])
    # Not Registered: u3 (1 user)
    mock_build_list.assert_any_call(list_header="‼️ **Participants checked-in but not registered:**", participants=['UserC'])
    assert mock_build_list.call_count == 2

    # 3. Check final message content (should include BOTH sections, separated by newline)
    expected_not_checked_in = "--- 🔍 **Participants not yet checked-in:** (1 users) ---"
    expected_not_registered = "--- ‼️ **Participants checked-in but not registered:** (1 users) ---"

    # This assertion verifies the new logic: content = f"{not_checked_in_message}\n{not_registered_message}"
    # since non_registered_participants is NOT empty/falsy
    assert response.content == f"{expected_not_checked_in}\n{expected_not_registered}"
    assert response.allowed_mentions is None


@patch(f'{COMMAND_MODULE}.message_helper.build_participants_list') # New Patch
@patch(f'{COMMAND_MODULE}._verify_has_organizer_role', return_value=None)
@patch(f'{DB_HELPER_PATH}.get_server_event_data_or_fail')
def test_show_not_checked_in_success_only_not_checked_in_list(
    mock_get_event_data,
    mock_verify_role,
    mock_build_list, # The mock is now injected here
    mock_discord_event,
    mock_aws_services
):
    """
    Tests when 'not registered' list is EMPTY.
    Verifies that the conditional logic prevents the empty not_registered_message from being appended.
    """
    # Arrange
    MOCK_EVENT_DATA = MockEventData(
        registered={'u1': 'UserA', 'u2': 'UserB'},
        checked_in={'u2': 'UserB'} # u3 is missing, so not registered list is empty
    )
    mock_get_event_data.return_value = MOCK_EVENT_DATA

    # Configure the mock's side effect directly here
    mock_build_list.side_effect = lambda list_header, participants: f"--- {list_header} ({len(participants)} users) ---"

    # Act
    response = check_in_commands.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    # 1. Check build_participants_list calls
    # Not Checked In: u1 (1 user)
    mock_build_list.assert_any_call(list_header="🔍 **Participants not yet checked-in:**", participants=['UserA'])
    assert mock_build_list.call_count == 1

    # 2. Check final message content (should include ONLY the first section)
    expected_not_checked_in = "--- 🔍 **Participants not yet checked-in:** (1 users) ---\n👍 No unexpected check-ins"

    # This assertion verifies the new logic: content = not_checked_in_message
    # since non_registered_participants is empty/falsy
    assert response.content == expected_not_checked_in


@patch(f'{COMMAND_MODULE}.message_helper.build_participants_list') # New Patch
@patch(f'{COMMAND_MODULE}._verify_has_organizer_role', return_value=None)
@patch(f'{DB_HELPER_PATH}.get_server_event_data_or_fail')
def test_show_not_checked_in_success_no_lists_empty_data(
    mock_get_event_data,
    mock_verify_role,
    mock_build_list, # The mock is now injected here
    mock_discord_event,
    mock_aws_services
):
    """Tests when both lists are empty (e.g., no one registered or checked in)."""
    # Arrange
    MOCK_EVENT_DATA = MockEventData(
        registered={},
        checked_in={}
    )
    mock_get_event_data.return_value = MOCK_EVENT_DATA

    # Configure the mock's side effect directly here
    mock_build_list.side_effect = lambda list_header, participants: f"--- {list_header} ({len(participants)} users) ---"

    # Act
    response = check_in_commands.show_not_checked_in(mock_discord_event, mock_aws_services)

    # 2. Check final message content (should include ONLY the first section)
    expected_not_checked_in = "✅ All registered participants have checked-in\n👍 No unexpected check-ins"

    # This assertion verifies the new logic: content = not_checked_in_message
    # since non_registered_participants is empty/falsy
    assert response.content == expected_not_checked_in


# --- Failure Tests ---

@patch(f'{COMMAND_MODULE}._verify_has_organizer_role')
def test_show_not_checked_in_fail_organizer_role(
    mock_verify_role,
    mock_discord_event,
    mock_aws_services
):
    """Tests failure when the organizer role check returns an error message."""
    # Arrange
    expected_response = ResponseMessage(content="Permission Denied")
    mock_verify_role.return_value = expected_response

    # Act
    response = check_in_commands.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response


@patch(f'{COMMAND_MODULE}._verify_has_organizer_role', return_value=None)
@patch(f'{DB_HELPER_PATH}.get_server_event_data_or_fail')
def test_show_not_checked_in_fail_event_data_retrieval(
    mock_get_event_data,
    mock_verify_role,
    mock_discord_event,
    mock_aws_services
):
    """Tests failure when event data retrieval returns an error message."""
    # Arrange
    expected_response = ResponseMessage(content="Event Data Missing/Error")
    mock_get_event_data.return_value = expected_response

    # Act
    response = check_in_commands.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    assert response is expected_response
