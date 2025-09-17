from commands.models.response_message import ResponseMessage

def check_in_user(event_body: dict) -> ResponseMessage:
    return ResponseMessage(content="Checking in!")

