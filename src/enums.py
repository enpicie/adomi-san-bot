from enum import Enum

class EventMode(str, Enum):
    SERVER_WIDE = "server_wide"
    PER_CHANNEL = "per_channel"
