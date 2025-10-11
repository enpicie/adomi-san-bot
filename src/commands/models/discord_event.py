class DiscordEvent:
    event_body: dict

    def __init__(self, event_body: dict):
        self.event_body = event_body

    def _get_event_field(self, *keys: str) -> any:
        """Access a nested field in `self.event_body` by path and return the value.

        Raises KeyError("Missing required field: a.b.c") if any segment is missing or not a dict.
        """
        cur = self.event_body
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                raise KeyError(f"Missing required field: {'.'.join(keys)}")
            cur = cur[k]
        return cur

    def get_command_name(self) -> str:
        return self._get_event_field("data", "name")

    def get_server_id(self) -> str:
        return self._get_event_field("guild_id")

    def get_channel_id(self) -> str:
        return self._get_event_field("channel_id")

    def get_user_id(self) -> str:
        return self._get_event_field("member", "user", "id")

    def get_user_name(self) -> str:
        return self._get_event_field("member", "user", "username")
