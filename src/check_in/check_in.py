from discord import Message

def check_in_user(event_body: dict) -> Message:
    return Message(content="Checking in!")

