from typing import Optional

import utils.adomin_messages as adomin_messages
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
            content=adomin_messages.REQUIRE_MANAGE_SERVER
        )

def require_organizer_role(server_config: ServerConfig, event: DiscordEvent) -> Optional[ResponseMessage]:
    if server_config.organizer_role not in event.get_user_roles():
        return ResponseMessage(
            content=adomin_messages.REQUIRE_ORGANIZER_ROLE
        )
