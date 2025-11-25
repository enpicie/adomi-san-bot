from typing import Optional

from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.server_config import ServerConfig

# Permissions Constants
MANAGE_SERVER_BIT = 0x20 # 1 << 5

# Per Discord Docs: https://discord.com/developers/docs/topics/permissions#permissions-bitwise-permission-flags
# Check permissions by doing bitwise AND with the permission integer.
# Each permission corresponds to 1 << x where x is the bit position.

def require_manage_server_permission(event: DiscordEvent) -> Optional[ResponseMessage]:
    """
    Checks if the given permission integer includes the 'Manage Server' permission.
    'Manage Server' permission bit is 0x20 (32 in decimal).
    """
    has_permission = (event.get_user_permission_int() & MANAGE_SERVER_BIT) != 0
    if not has_permission:
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to set things up for this server."
        )


def require_organizer_role(server_config: ServerConfig, event: DiscordEvent) -> Optional[ResponseMessage]:
    if server_config.organizer_role not in event.get_user_roles():
        return ResponseMessage(
            content="❌ You don't have permission to clear check-ins. "
                    "Only users with the server's designated organizer role can do this."
        )
