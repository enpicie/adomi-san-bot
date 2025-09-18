# This is to make it easier to access participant information
class Participant:
    def __init__(self, startgg_id, tag, discord_id = None, discord_user = None):
        self.startgg_id = startgg_id # ID in the start.gg bracket
        self.tag = tag # Gamer tag
        self.discord_id = discord_id # Discord ID
        self.discord_user = discord_user # Discord Username