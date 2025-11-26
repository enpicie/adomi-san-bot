import pytest
from unittest.mock import Mock, patch, call
from botocore.exceptions import ClientError
from typing import Optional

# The module under test is assumed to be imported from your project root (src)
from commands.check_in import check_in_commands as target_module
from database.models.event_data import EventData
from database.models.participant import Participant
from commands.models.response_message import ResponseMessage

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
    event.get_command_input_value.side_effect = lambda key: False if key == "ping_users" else None # Default to No ping
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
    """Tests successful retrieval and display of check-ins, verifying the use of build_participants_list and silent pings."""
    # Setup mocks
    mock_verify_role.return_value = None # Permission success
    MOCK_CONTENT = "Mock List Content"
    mock_message_helper.build_participants_list.return_value = MOCK_CONTENT

    # 1. Define checked_in map
    checked_in_map = {
        "U1": {"user_id": "U1", "display_name": "Alice"},
        "U2": {"user_id": "U2", "display_name": "Bob"}
    }
    mock_event_data = Mock(checked_in=checked_in_map)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Execute
    response = target_module.show_checked_in(mock_discord_event, mock_aws_services)

    # Assertions
    assert response.content == MOCK_CONTENT
    # Check that .with_silent_pings() was called
    assert response.allowed_mentions is not None

    # Check that build_participants_list was called correctly
    mock_message_helper.build_participants_list.assert_called_once()
    call_args = mock_message_helper.build_participants_list.call_args[1]
    assert call_args["list_header"] == "✅ **Checked-in Users:**"
    # We check that the values (the participant dictionaries) are passed
    assert list(call_args["participants"]) == list(checked_in_map.values())


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
    # The logic in clear_checked_in is: if event_data_result.participant_role: update_item. Since role is None, update_item is skipped.
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


# --- Tests for show_not_checked_in (Updated for combined output) ---

@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role')
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_permission_fail(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """Tests failure when permission check fails."""
    expected_response = ResponseMessage(content="No Permission")
    mock_verify_role.return_value = expected_response

    result = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    assert result is expected_response
    mock_db_helper.get_server_event_data_or_fail.assert_not_called()

@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_data_fail(mock_db_helper, mock_discord_event, mock_aws_services):
    """Tests failure when event data retrieval fails."""
    expected_response = ResponseMessage(content="Data Error")
    mock_db_helper.get_server_event_data_or_fail.return_value = expected_response

    result = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    assert result is expected_response

@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_success_combined_output(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """
    Tests the combined output of 'Registered but not Checked-In' and 'Checked-In but not Registered'
    with silent pings (default command behavior).
    """
    # Arrange Test Data
    MOCK_REGISTERED_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice (Registered & Checked)"},
        "U2": {"user_id": "U2", "display_name": "Bob (Missing Check-in)"},
        "U3": {"user_id": "U3", "display_name": "Charlie (Missing Check-in)"},
    }
    MOCK_CHECKED_IN_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice"},
        "U4": {"user_id": "U4", "display_name": "Dave (Unregistered Check-in)"},
        "U5": {"user_id": "U5", "display_name": "Eve (Unregistered Check-in)"},
    }

    # Expected differences
    # Registered - Checked In (Not Checked In) = {U2, U3}
    NOT_CHECKED_IN_EXPECTED_PARTICIPANTS = [MOCK_REGISTERED_DATA["U2"], MOCK_REGISTERED_DATA["U3"]]
    MOCK_NOT_CHECKED_IN_CONTENT = "🔍 **Participants not yet checked-in:**\n- Bob\n- Charlie"

    # Checked In - Registered (Not Registered) = {U4, U5}
    NOT_REGISTERED_EXPECTED_PARTICIPANTS = [MOCK_CHECKED_IN_DATA["U4"], MOCK_CHECKED_IN_DATA["U5"]]
    MOCK_NOT_REGISTERED_CONTENT = "‼️ **Participants checked-in but not registered:**\n- Dave\n- Eve"

    EXPECTED_FINAL_CONTENT = f"{MOCK_NOT_CHECKED_IN_CONTENT}\n{MOCK_NOT_REGISTERED_CONTENT}"

    mock_event_data = Mock(registered=MOCK_REGISTERED_DATA, checked_in=MOCK_CHECKED_IN_DATA)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Set side effect for two sequential calls to build_participants_list
    mock_message_helper.build_participants_list.side_effect = [
        MOCK_NOT_CHECKED_IN_CONTENT,  # First call: Not Checked In
        MOCK_NOT_REGISTERED_CONTENT   # Second call: Not Registered
    ]

    # Act
    response = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assert Final Response
    assert response.content == EXPECTED_FINAL_CONTENT
    assert response.allowed_mentions is not None # Silent pings (default False input)

    # Assert Call 1 (Not Checked In)
    # Since order is not guaranteed for sets, we convert the lists of dicts to hashable sets for comparison
    assert mock_message_helper.build_participants_list.call_args_list[0][1]["list_header"] == "🔍 **Participants not yet checked-in:**"
    call1_participants = mock_message_helper.build_participants_list.call_args_list[0][1]["participants"]
    hashable_call1 = {tuple(sorted(p.items())) for p in call1_participants}
    hashable_expected1 = {tuple(sorted(p.items())) for p in NOT_CHECKED_IN_EXPECTED_PARTICIPANTS}
    assert hashable_call1 == hashable_expected1

    # Assert Call 2 (Not Registered)
    assert mock_message_helper.build_participants_list.call_args_list[1][1]["list_header"] == "‼️ **Participants checked-in but not registered:**"
    call2_participants = mock_message_helper.build_participants_list.call_args_list[1][1]["participants"]
    hashable_call2 = {tuple(sorted(p.items())) for p in call2_participants}
    hashable_expected2 = {tuple(sorted(p.items())) for p in NOT_REGISTERED_EXPECTED_PARTICIPANTS}
    assert hashable_call2 == hashable_expected2


@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_success_ping_enabled(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """
    Tests the combined output with explicit ping enabled (allowed_mentions should be None).
    Also ensures the message is correctly generated (using the same content as the combined test).
    """
    # Arrange Test Data
    MOCK_REGISTERED_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice (Registered & Checked)"},
        "U2": {"user_id": "U2", "display_name": "Bob (Missing Check-in)"},
    }
    MOCK_CHECKED_IN_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice"},
        "U4": {"user_id": "U4", "display_name": "Dave (Unregistered Check-in)"},
    }

    MOCK_NOT_CHECKED_IN_CONTENT = "🔍 **Participants not yet checked-in:**\n- Bob"
    MOCK_NOT_REGISTERED_CONTENT = "‼️ **Participants checked-in but not registered:**\n- Dave"
    EXPECTED_FINAL_CONTENT = f"{MOCK_NOT_CHECKED_IN_CONTENT}\n{MOCK_NOT_REGISTERED_CONTENT}"

    mock_event_data = Mock(registered=MOCK_REGISTERED_DATA, checked_in=MOCK_CHECKED_IN_DATA)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Set command input to True (requesting pings)
    mock_discord_event.get_command_input_value.side_effect = lambda key: True if key == "ping_users" else None

    # Set side effect for two sequential calls to build_participants_list
    mock_message_helper.build_participants_list.side_effect = [
        MOCK_NOT_CHECKED_IN_CONTENT,
        MOCK_NOT_REGISTERED_CONTENT
    ]

    # Act
    response = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assert Final Response
    assert response.content == EXPECTED_FINAL_CONTENT
    assert response.allowed_mentions is None # Pings enabled

@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_only_registered_missing(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """
    Tests the case where only 'Registered but not Checked-In' users exist, and the final message
    is correctly composed without the separator.
    """
    # Arrange Test Data
    MOCK_REGISTERED_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice (Missing Check-in)"},
    }
    MOCK_CHECKED_IN_DATA = {} # No checked-in users at all

    MOCK_NOT_CHECKED_IN_CONTENT = "🔍 **Participants not yet checked-in:**\n- Alice"
    MOCK_NOT_REGISTERED_CONTENT = "‼️ **Participants checked-in but not registered:**\n" # Empty second list, will be truthy but contain only the header and a newline.

    # When not_registered_message is generated, it will be the header + newline (which is truthy).
    # The command logic is: content = f"{not_checked_in_message}\n{not_registered_message}" if not_registered_message else not_checked_in_message
    # Since MOCK_NOT_REGISTERED_CONTENT is truthy, it concatenates.
    EXPECTED_FINAL_CONTENT = f"{MOCK_NOT_CHECKED_IN_CONTENT}\n{MOCK_NOT_REGISTERED_CONTENT}"

    mock_event_data = Mock(registered=MOCK_REGISTERED_DATA, checked_in=MOCK_CHECKED_IN_DATA)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Set side effect for two sequential calls to build_participants_list
    mock_message_helper.build_participants_list.side_effect = [
        MOCK_NOT_CHECKED_IN_CONTENT,
        MOCK_NOT_REGISTERED_CONTENT
    ]

    # Act
    response = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assert Final Response
    assert response.content == EXPECTED_FINAL_CONTENT
    assert response.allowed_mentions is not None


@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_only_unregistered_check_ins(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """
    Tests the case where only 'Checked-In but not Registered' users exist.
    """
    # Arrange Test Data
    MOCK_REGISTERED_DATA = {} # No registered users
    MOCK_CHECKED_IN_DATA = {
        "U1": {"user_id": "U1", "display_name": "Bob (Unregistered Check-in)"},
    }

    MOCK_NOT_CHECKED_IN_CONTENT = "🔍 **Participants not yet checked-in:**\n" # Empty first list
    MOCK_NOT_REGISTERED_CONTENT = "‼️ **Participants checked-in but not registered:**\n- Bob"
    EXPECTED_FINAL_CONTENT = f"{MOCK_NOT_CHECKED_IN_CONTENT}\n{MOCK_NOT_REGISTERED_CONTENT}"

    mock_event_data = Mock(registered=MOCK_REGISTERED_DATA, checked_in=MOCK_CHECKED_IN_DATA)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Set side effect for two sequential calls to build_participants_list
    mock_message_helper.build_participants_list.side_effect = [
        MOCK_NOT_CHECKED_IN_CONTENT,
        MOCK_NOT_REGISTERED_CONTENT
    ]

    # Act
    response = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assert Final Response
    assert response.content == EXPECTED_FINAL_CONTENT
    assert response.allowed_mentions is not None

@patch('commands.check_in.check_in_commands.message_helper')
@patch('commands.check_in.check_in_commands._verify_has_organizer_role', return_value=None)
@patch('commands.check_in.check_in_commands.db_helper')
def test_show_not_checked_in_all_users_aligned(mock_db_helper, mock_verify_role, mock_message_helper, mock_discord_event, mock_aws_services):
    """Tests the case where registered and checked_in sets are identical (no differences)."""
    # Arrange Test Data
    MOCK_REGISTERED_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice"},
    }
    MOCK_CHECKED_IN_DATA = {
        "U1": {"user_id": "U1", "display_name": "Alice"},
    }

    MOCK_NOT_CHECKED_IN_CONTENT = "🔍 **Participants not yet checked-in:**\n" # Empty first list
    MOCK_NOT_REGISTERED_CONTENT = "‼️ **Participants checked-in but not registered:**\n" # Empty second list

    # The command logic is: content = f"{not_checked_in_message}\n{not_registered_message}" if not_registered_message else not_checked_in_message
    # Since not_registered_message is truthy (header + newline), it concatenates.
    EXPECTED_FINAL_CONTENT = f"{MOCK_NOT_CHECKED_IN_CONTENT}\n{MOCK_NOT_REGISTERED_CONTENT}"

    mock_event_data = Mock(registered=MOCK_REGISTERED_DATA, checked_in=MOCK_CHECKED_IN_DATA)
    mock_db_helper.get_server_event_data_or_fail.return_value = mock_event_data

    # Set side effect for two sequential calls to build_participants_list
    mock_message_helper.build_participants_list.side_effect = [
        MOCK_NOT_CHECKED_IN_CONTENT,
        MOCK_NOT_REGISTERED_CONTENT
    ]

    # Act
    response = target_module.show_not_checked_in(mock_discord_event, mock_aws_services)

    # Assert Final Response
    assert response.content == EXPECTED_FINAL_CONTENT
    assert response.allowed_mentions is not None

    # Assert call arguments are empty lists for both calls
    assert len(mock_message_helper.build_participants_list.call_args_list[0][1]["participants"]) == 0
    assert len(mock_message_helper.build_participants_list.call_args_list[1][1]["participants"]) == 0
