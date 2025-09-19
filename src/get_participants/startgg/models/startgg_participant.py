# This is to make it easier to access participant information
class StartggParticipant:
    def __init__(self, startgg_id, tag, discord_id = None, discord_user = None):
        self.startgg_id = startgg_id 
        self.tag = tag 
        self.discord_id = discord_id 
        self.discord_user = discord_user 