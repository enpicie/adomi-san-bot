from dataclasses import dataclass

@dataclass
class StartggParticipant:
    startgg_id: str
    username: str
    discord_id: str = None
    discord_user: str = None

    def __init__(self, startgg_id, username, discord_id = None, discord_user = None):
        self.startgg_id = startgg_id
        self.username = username
        self.discord_id = discord_id
        self.discord_user = discord_user
