# Permissions Constants
MANAGE_SERVER_BIT = 0x20 # 1 << 5

# Per Discord Docs: https://discord.com/developers/docs/topics/permissions#permissions-bitwise-permission-flags
# Check permissions by doing bitwise AND with the permission integer.
# Each permission corresponds to 1 << x where x is the bit position.

def has_manage_server_permission(permission_int: int) -> bool:
    """
    Checks if the given permission integer includes the 'Manage Server' permission.
    'Manage Server' permission bit is 0x20 (32 in decimal).
    """
    return (permission_int & MANAGE_SERVER_BIT) != 0
