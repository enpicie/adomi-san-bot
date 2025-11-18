from unittest.mock import MagicMock
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
import commands.cleanup.commands as cleanup

def mock_server():
    return DiscordEvent(
        {
            "guild_id": 925,
            "channel_id": 1
        }
    )

def test_delete_server(monkeypatch):
    mock_table = MagicMock()
    event = mock_server()

    response = cleanup.delete_server(event, mock_table)

    # Assertions
    assert isinstance(response, ResponseMessage)
    expected_message = f"Deleted config for server: {event.get_server_id()}!"
    assert response.content == expected_message