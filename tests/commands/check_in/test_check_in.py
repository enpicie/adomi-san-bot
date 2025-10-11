import pytest
from unittest.mock import MagicMock
from moto import mock_dynamodb2
import boto3
from commands.check_in import check_in_user
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

@pytest.fixture
def mock_dynamodb():
    with mock_dynamodb2():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='CheckIns',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        yield table
        table.delete()

def test_check_in_user(mock_dynamodb):
    table = mock_dynamodb
    event = DiscordEvent(user_id="123", username="Alice", server_id="1", channel_id="10")
    response = check_in_user(event, table)
    assert isinstance(response, ResponseMessage)
    assert "Checked in" in response.content
