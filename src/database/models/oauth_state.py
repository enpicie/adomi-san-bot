from dataclasses import dataclass, field
from typing import Dict, Any

from database.models.subscriptable_mixin import SubscriptableMixin


@dataclass
class OAuthState(SubscriptableMixin):
    class Keys:
        PK_PREFIX = "OAUTH_STATE#"
        SK = "STATE"
        TTL_SECONDS = 600  # 10 minutes

        DISCORD_USER_ID = "discord_user_id"
        SERVER_ID = "server_id"
        CHANNEL_ID = "channel_id"
        EXPIRES_AT = "expires_at"

    discord_user_id: str = field(metadata={"db_key": Keys.DISCORD_USER_ID})
    server_id: str = field(metadata={"db_key": Keys.SERVER_ID})
    channel_id: str = field(metadata={"db_key": Keys.CHANNEL_ID})
    expires_at: int = field(metadata={"db_key": Keys.EXPIRES_AT})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> "OAuthState":
        return cls(
            discord_user_id=record[cls.Keys.DISCORD_USER_ID],
            server_id=record[cls.Keys.SERVER_ID],
            channel_id=record[cls.Keys.CHANNEL_ID],
            expires_at=record[cls.Keys.EXPIRES_AT],
        )
