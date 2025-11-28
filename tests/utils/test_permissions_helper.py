import pytest
from unittest.mock import Mock, call
from typing import Optional, NamedTuple

# Mock external models/types for type hinting and mocking purposes
class DiscordEvent:
    def get_user_permission_int(self) -> int: ...
    def get_user_roles(self) -> list[str]: ...

class ServerConfig:
    def __init__(self, organizer_role: str):
        self.organizer_role = organizer_role

class ResponseMessage:
    def __init__(self, content: str):
        self.content = content

# --- Function Definitions (from user's permissions_helper.py) ---

# Permissions Constants
MANAGE_SERVER_BIT = 0x20 # 1 << 5

def require_manage_server_permission(event: DiscordEvent) -> Optional[ResponseMessage]:
    """
    Checks if the given permission integer includes the 'Manage Server' permission.
    'Manage Server' permission bit is 0x20 (32 in decimal).
    """
    # Cast event to Mock for ease of testing in this context, though typically a real DiscordEvent is passed
    mock_event: Mock = event
    has_permission = (mock_event.get_user_permission_int() & MANAGE_SERVER_BIT) != 0
    if not has_permission:
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to set things up for this server."
        )
    return None

def require_organizer_role(server_config: ServerConfig, event: DiscordEvent) -> Optional[ResponseMessage]:
    """
    Checks if the user has the designated organizer role.
    """
    mock_event: Mock = event
    if server_config.organizer_role not in mock_event.get_user_roles():
        return ResponseMessage(
            content="❌ You don't have permission to clear check-ins. "
                    "Only users with the server's designated organizer role can do this."
        )
    return None

# --- Test Cases for require_manage_server_permission ---

class ManagePermissionTestCase(NamedTuple):
    name: str
    permission_int: int
    expected_is_error: bool
    description: str

MANAGE_PERM_TEST_CASES = [
    ManagePermissionTestCase(
        name="Lacks permission (0)",
        permission_int=0,
        expected_is_error=True,
        description="No permissions set, should fail."
    ),
    ManagePermissionTestCase(
        name="Has exact MANAGE_SERVER (0x20)",
        permission_int=MANAGE_SERVER_BIT,
        expected_is_error=False,
        description="Only the MANAGE_SERVER bit is set, should pass."
    ),
    ManagePermissionTestCase(
        name="Has MANAGE_SERVER with other bits (0x2F)",
        permission_int=0x20 | 0x08 | 0x04 | 0x02 | 0x01,
        expected_is_error=False,
        description="MANAGE_SERVER bit is set, should pass."
    ),
    ManagePermissionTestCase(
        name="Lacks MANAGE_SERVER, has others (0x10)",
        permission_int=0x10, # MANAGE_CHANNELS
        expected_is_error=True,
        description="A different MANAGE permission bit is set, should fail."
    ),
]

@pytest.mark.parametrize("case", MANAGE_PERM_TEST_CASES, ids=[c.name for c in MANAGE_PERM_TEST_CASES])
def test_require_manage_server_permission(case: ManagePermissionTestCase):
    """
    Tests the outcome of require_manage_server_permission based on the user's permission integer.
    """
    # Arrange
    mock_event = Mock(spec=DiscordEvent)
    mock_event.get_user_permission_int.return_value = case.permission_int

    # Act
    response = require_manage_server_permission(mock_event)

    # Assert
    if case.expected_is_error:
        assert isinstance(response, ResponseMessage)
        assert "Manage Server" in response.content
    else:
        assert response is None

# --- Test Cases for require_organizer_role ---

class OrganizerRoleTestCase(NamedTuple):
    name: str
    organizer_role_id: str
    user_roles: list[str]
    expected_is_error: bool
    description: str

ORGANIZER_ROLE_TEST_CASES = [
    OrganizerRoleTestCase(
        name="User is organizer",
        organizer_role_id="ROLE_ORG",
        user_roles=["ROLE_MEMBER", "ROLE_ORG", "ROLE_ADMIN"],
        expected_is_error=False,
        description="User's roles list contains the organizer role ID."
    ),
    OrganizerRoleTestCase(
        name="User is not organizer",
        organizer_role_id="ROLE_ORG",
        user_roles=["ROLE_MEMBER", "ROLE_ADMIN"],
        expected_is_error=True,
        description="User's roles list does not contain the organizer role ID."
    ),
    OrganizerRoleTestCase(
        name="Empty user roles list",
        organizer_role_id="ROLE_ORG",
        user_roles=[],
        expected_is_error=True,
        description="User has no roles, should fail."
    ),
    OrganizerRoleTestCase(
        name="Organizer role is None/empty string (edge case)",
        organizer_role_id="",
        user_roles=["ROLE_MEMBER"],
        expected_is_error=True, # Assuming an empty string role means no one should pass, or it's unconfigured
        description="Server config has an empty organizer role ID."
    ),
]

@pytest.mark.parametrize("case", ORGANIZER_ROLE_TEST_CASES, ids=[c.name for c in ORGANIZER_ROLE_TEST_CASES])
def test_require_organizer_role(case: OrganizerRoleTestCase):
    """
    Tests the outcome of require_organizer_role based on the user's roles vs. the configured role.
    """
    # Arrange
    mock_server_config = ServerConfig(organizer_role=case.organizer_role_id)
    mock_event = Mock(spec=DiscordEvent)
    mock_event.get_user_roles.return_value = case.user_roles

    # Act
    response = require_organizer_role(mock_server_config, mock_event)

    # Assert
    if case.expected_is_error:
        assert isinstance(response, ResponseMessage)
        assert "organizer role can do this" in response.content
    else:
        assert response is None
