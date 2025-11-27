import pytest
from typing import List, Dict, Any

import utils.message_helper as message_helper

from database.models.participant import Participant

def test_get_user_ping():
    user_id = "123"
    expected = "<@123>"
    assert message_helper.get_user_ping(user_id) == expected

def test_get_channel_mention():
    channel_id = "456"
    expected = "<#456>"
    assert message_helper.get_channel_mention(channel_id) == expected

def test_build_participants_list_empty():
    """Tests list building with an empty participant list."""
    header = "Attendees"
    participants = []
    expected = "Attendees\n"
    assert message_helper.build_participants_list(header, participants) == expected

def test_build_participants_list_discord_users():
    """Tests list building with only standard Discord users (should use pings)."""
    header = "Discord Members"
    participants = [
        {Participant.Keys.USER_ID: "100", Participant.Keys.DISPLAY_NAME: "Alice"},
        {Participant.Keys.USER_ID: "200", Participant.Keys.DISPLAY_NAME: "Bob"},
    ]
    expected = "Discord Members\n- <@100>: Alice\n- <@200>: Bob"
    assert message_helper.build_participants_list(header, participants) == expected

def test_build_participants_list_placeholder_users():
    """Tests list building with only placeholder users (should use display name only)."""
    header = "External Guests"
    participants = [
        {Participant.Keys.USER_ID: Participant.DEFAULT_ID_PLACEHOLDER, Participant.Keys.DISPLAY_NAME: "Guest 1"},
        {Participant.Keys.USER_ID: Participant.DEFAULT_ID_PLACEHOLDER, Participant.Keys.DISPLAY_NAME: "Guest 2"},
    ]
    expected = "External Guests\n- Guest 1\n- Guest 2"
    assert message_helper.build_participants_list(header, participants) == expected

def test_build_participants_list_mixed_users():
    """Tests list building with a mix of Discord and placeholder users."""
    header = "All Attendees"
    participants = [
        {Participant.Keys.USER_ID: "300", Participant.Keys.DISPLAY_NAME: "Charlie"},
        {Participant.Keys.USER_ID: Participant.DEFAULT_ID_PLACEHOLDER, Participant.Keys.DISPLAY_NAME: "External Reporter"},
        {Participant.Keys.USER_ID: "400", Participant.Keys.DISPLAY_NAME: "Dave"},
    ]
    expected = "All Attendees\n- <@300>: Charlie\n- External Reporter\n- <@400>: Dave"
    assert message_helper.build_participants_list(header, participants) == expected
