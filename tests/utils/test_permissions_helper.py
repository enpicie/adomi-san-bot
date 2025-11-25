import pytest
from typing import NamedTuple

# Mock the constants and function locally for isolated testing,
# assuming they would be in a module named 'utils.permissions_helper'
# in the actual project structure.

# Permissions Constants (as defined in the user's snippet)
MANAGE_SERVER_BIT = 0x20 # 1 << 5 (Decimal 32)

def has_manage_server_permission(permission_int: int) -> bool:
    """
    Checks if the given permission integer includes the 'Manage Server' permission.
    'Manage Server' permission bit is 0x20 (32 in decimal).
    """
    return (permission_int & MANAGE_SERVER_BIT) != 0

# --- Test Data Structure ---

class PermissionTestCase(NamedTuple):
    """A structure for holding test case data."""
    name: str
    permission_int: int
    expected_result: bool
    description: str

# --- Test Cases ---

# A few common permission bits for context:
# 0x01 (1) - CREATE_INSTANT_INVITE
# 0x02 (2) - KICK_MEMBERS
# 0x04 (4) - BAN_MEMBERS
# 0x08 (8) - ADMINISTRATOR
# 0x10 (16) - MANAGE_CHANNELS
# 0x20 (32) - MANAGE_SERVER (The one we are testing)

TEST_CASES = [
    PermissionTestCase(
        name="No permissions set (0)",
        permission_int=0,
        expected_result=False,
        description="A permission integer of 0 should always fail."
    ),
    PermissionTestCase(
        name="Exact MANAGE_SERVER bit set (0x20)",
        permission_int=MANAGE_SERVER_BIT, # 32
        expected_result=True,
        description="Only the MANAGE_SERVER bit is set."
    ),
    PermissionTestCase(
        name="MANAGE_SERVER with other permissions (0x23)",
        permission_int=0x20 | 0x02 | 0x01, # MANAGE_SERVER + KICK_MEMBERS + CREATE_INSTANT_INVITE
        expected_result=True,
        description="MANAGE_SERVER bit is set along with other bits."
    ),
    PermissionTestCase(
        name="Only ADMINISTRATOR bit set (0x08)",
        permission_int=0x08, # ADMINISTRATOR
        expected_result=False,
        description="ADMNISTRATOR does not imply MANAGE_SERVER (if not used as an aggregate permission)."
    ),
    PermissionTestCase(
        name="Only MANAGE_CHANNELS bit set (0x10)",
        permission_int=0x10,
        expected_result=False,
        description="A different MANAGE permission bit is set."
    ),
    PermissionTestCase(
        name="All bits set below MANAGE_SERVER (0x1F)",
        permission_int=0x01 | 0x02 | 0x04 | 0x08 | 0x10,
        expected_result=False,
        description="Tests a value just below the target bit."
    ),
    PermissionTestCase(
        name="Full permission set (including MANAGE_SERVER)",
        permission_int=0xFFFFFFFF, # Simulate all 32 bits set
        expected_result=True,
        description="All bits set, including the target bit."
    ),
]

# --- Pytest Test Function ---

@pytest.mark.parametrize("case", TEST_CASES, ids=[c.name for c in TEST_CASES])
def test_has_manage_server_permission(case: PermissionTestCase):
    """
    Tests the has_manage_server_permission function against various permission integer scenarios.
    """
    # Act
    result = has_manage_server_permission(case.permission_int)

    # Assert
    assert result == case.expected_result, \
        f"Case '{case.name}' failed: Input {hex(case.permission_int)} ({case.permission_int}) " \
        f"expected {case.expected_result}, but got {result}. ({case.description})"
