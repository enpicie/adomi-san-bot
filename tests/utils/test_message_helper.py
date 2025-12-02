import pytest
from typing import List, Dict, Any
from unittest.mock import patch

# The relative import path to the module being tested
import utils.message_helper as message_helper

# The Participant class definition
from database.models.participant import Participant


# --- Mock Dependencies (get_user_ping) ---

# Patching get_user_ping globally for all tests in this file
@patch('utils.message_helper.get_user_ping', side_effect=lambda user_id: f"<@{user_id}>")
class TestBuildParticipantsList:
    # We use a test class to encapsulate all tests using the same patch

    # Helper function to create Participant instances easily
    def _create_participant(self, display_name, user_id):
        # We must use the constructor which expects the actual data attributes
        return Participant(display_name=display_name, user_id=user_id)

    # --- Utility Tests (keeping them inside the class, though they don't strictly use the patch) ---

    def test_get_user_ping(self, mock_get_user_ping):
        """Tests the mock replacement for get_user_ping."""
        user_id = "123"
        expected = "<@123>"
        # The mock will now handle this, so we check the mock's side_effect behavior
        assert mock_get_user_ping(user_id) == expected

    # Note: get_channel_mention is often a standalone function and should not be mocked
    # but kept for completeness, assuming it's imported correctly.
    # We remove it from the class to avoid interference with the patch.
    # If the user insists on having it in the class, we'd adjust the patch decorator.
    pass


# --- Standalone Utility Tests (outside the patched class) ---

def test_get_channel_mention():
    """Tests the channel mention utility."""
    channel_id = "456"
    # Assuming get_channel_mention exists and returns the standard format
    expected = "<#456>"
    assert message_helper.get_channel_mention(channel_id) == expected


# --- Refactored Build List Tests ---

@patch('utils.message_helper.get_user_ping', side_effect=lambda user_id: f"<@{user_id}>")
def test_build_participants_list_empty(mock_get_user_ping):
    """Tests list building with an empty participant list (no numbers or sorting necessary)."""
    header = "Attendees"
    participants = []
    expected = "Attendees\n"
    assert message_helper.build_participants_list(header, participants) == expected


@patch('utils.message_helper.get_user_ping', side_effect=lambda user_id: f"<@{user_id}>")
def test_build_participants_list_discord_users_and_sorting(mock_get_user_ping):
    """Tests sorting and numbered list formatting for standard Discord users."""
    header = "Discord Members"

    # Input data is intentionally out of alphabetical order by display name
    participants = [
        Participant(user_id="200", display_name="Zed"),
        Participant(user_id="100", display_name="Alice"),
        Participant(user_id="300", display_name="Bob"),
    ]

    # Expected output should be sorted (Alice, Bob, Zed) and numbered (1., 2., 3.)
    expected = (
        "Discord Members\n"
        "1. <@100>: Alice\n"
        "2. <@300>: Bob\n"
        "3. <@200>: Zed"
    )
    assert message_helper.build_participants_list(header, participants) == expected

@patch('utils.message_helper.get_user_ping', side_effect=lambda user_id: f"<@{user_id}>")
def test_build_participants_list_placeholder_users_and_sorting(mock_get_user_ping):
    """Tests sorting and numbered list formatting for placeholder users."""
    header = "External Guests"

    # Input data is intentionally out of alphabetical order
    participants = [
        Participant(user_id=Participant.DEFAULT_ID_PLACEHOLDER, display_name="Guest Z"),
        Participant(user_id=Participant.DEFAULT_ID_PLACEHOLDER, display_name="Guest A"),
        Participant(user_id=Participant.DEFAULT_ID_PLACEHOLDER, display_name="Guest M"),
    ]

    # Expected output should be sorted (Guest A, Guest M, Guest Z) and numbered
    expected = (
        "External Guests\n"
        "1. Guest A\n"
        "2. Guest M\n"
        "3. Guest Z"
    )
    assert message_helper.build_participants_list(header, participants) == expected

@patch('utils.message_helper.get_user_ping', side_effect=lambda user_id: f"<@{user_id}>")
def test_build_participants_list_mixed_users_and_sorting(mock_get_user_ping):
    """Tests list building with a mix of Discord and placeholder users, ensuring proper sorting."""
    header = "All Attendees"

    # Input data (Unsorted by Display Name)
    participants = [
        Participant(user_id="400", display_name="Dave"),
        Participant(user_id=Participant.DEFAULT_ID_PLACEHOLDER, display_name="External Reporter"),
        Participant(user_id="300", display_name="Charlie"),
        Participant(user_id="500", display_name="Adam"),
    ]

    # Expected output (Sorted by Display Name: Adam, Charlie, Dave, External Reporter)
    expected = (
        "All Attendees\n"
        "1. <@500>: Adam\n"
        "2. <@300>: Charlie\n"
        "3. <@400>: Dave\n"
        "4. External Reporter" # Placeholder should not have a ping, just the number and name
    )
    assert message_helper.build_participants_list(header, participants) == expected
