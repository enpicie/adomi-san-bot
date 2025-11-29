from unittest.mock import Mock, patch

import commands.announce.announce_commands as announce_commands
import database.dynamodb_utils as db_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from aws_services import AWSServices

@patch('database.dynamodb_utils.build_server_pk')
@patch('utils.message_helper.get_role_ping')
@patch('database.models.event_data.EventData.from_dynamodb')
def test_announce_event(mock_from_db, mock_role_ping, mock_build_pk):
    """Test announcing an event with participant ping"""
    # Setup mocks
    mock_event = Mock(spec=DiscordEvent)
    mock_event.get_server_id.return_value = "server_123"
    mock_event.get_command_input_value.side_effect = lambda key: {
        "announce_type": "start",
        "ping_participants": True
    }[key]
    
    mock_aws_services = Mock(spec=AWSServices)
    mock_aws_services.dynamotb_table = Mock()
    mock_aws_services.dynamotb_table.get_item.return_value = {}
    
    mock_build_pk.return_value = "SERVER#server_123"
    mock_role_ping.return_value = "<@&123456789>"
    
    mock_event_data = Mock(spec=EventData)
    mock_event_data.participant_role = "123456789"
    mock_event_data.start_message = "Event is starting now!"
    mock_from_db.return_value = mock_event_data
    
    # Execute
    result = announce_commands.announce_event(mock_event, mock_aws_services)
    
    # Assert
    assert isinstance(result, ResponseMessage)
    assert result.content == "<@&123456789>\nEvent is starting now!"
    mock_aws_services.dynamotb_table.get_item.assert_called_once()
    mock_role_ping.assert_called_once_with("123456789")


@patch('database.dynamodb_utils.build_server_pk')
@patch('database.models.event_data.EventData.Keys.SK_SERVER', 'SERVER')
def test_set_announce(mock_get_pk):
    """Test setting an event announcement message"""
    # Setup mocks
    mock_event = Mock(spec=DiscordEvent)
    mock_event.get_server_id.return_value = "server_123"
    mock_event.get_command_input_value.side_effect = lambda key: {
        "message_text": "Welcome to the event!",
        "announce_type": "start"
    }[key]
    
    mock_aws_services = Mock(spec=AWSServices)
    mock_aws_services.dynamotb_table = Mock()
    
    mock_get_pk.return_value = "SERVER#server_123"
    
    # Execute
    result = announce_commands.set_event_message(mock_event, mock_aws_services)
    
    # Assert
    assert isinstance(result, ResponseMessage)
    assert result.content == "✅ Set the start announcement for the current event!"
    mock_aws_services.dynamotb_table.update_item.assert_called_once()
    
    # Verify update_item was called with correct parameters
    call_args = mock_aws_services.dynamotb_table.update_item.call_args
    assert call_args[1]['Key']['PK'] == "SERVER#server_123"
    assert call_args[1]['ExpressionAttributeValues'][':msg'] == "Welcome to the event!"


@patch('database.dynamodb_utils.build_server_pk')
@patch('database.models.event_data.EventData.Keys.SK_SERVER', 'SERVER')
def test_set_announce_clear(mock_get_pk):
    """Test clearing an event announcement message by setting it to empty string"""
    # Setup mocks
    mock_event = Mock(spec=DiscordEvent)
    mock_event.get_server_id.return_value = "server_123"
    mock_event.get_command_input_value.side_effect = lambda key: {
        "message_text": "",
        "announce_type": "end"
    }[key]
    
    mock_aws_services = Mock(spec=AWSServices)
    mock_aws_services.dynamotb_table = Mock()
    
    mock_get_pk.return_value = "SERVER#server_123"
    
    # Execute
    result = announce_commands.set_event_message(mock_event, mock_aws_services)
    
    # Assert
    assert isinstance(result, ResponseMessage)
    assert result.content == "✅ Set the end announcement for the current event!"
    mock_aws_services.dynamotb_table.update_item.assert_called_once()
    
    # Verify empty string was passed to DynamoDB
    call_args = mock_aws_services.dynamotb_table.update_item.call_args
    assert call_args[1]['ExpressionAttributeValues'][':msg'] == ""