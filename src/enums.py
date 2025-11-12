from enum import Enum

class EventMode(str, Enum):
    SERVER_WIDE = "server-wide"
    PER_CHANNEL = "per-channel"
