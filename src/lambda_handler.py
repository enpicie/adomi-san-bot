import json
import traceback

import bot
import constants
import utils.discord_auth_helper as auth_helper
from aws_client import get_aws_services
from commands.models.response_message import ResponseMessage
from enums import DiscordInteractionType, DiscordCallbackType


def lambda_handler(event, context):
    print(f"Received Event: {event}")

    try:
        auth_helper.verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}") from e

    if not event["body"]:
        return {"message": "Request is not Lambda event: 'body-json' not found"}

    body = json.loads(event["body"])

    if auth_helper.is_ping_pong(body):
        print("discord_auth_helper.is_ping_pong: True")
        response = constants.PING_PONG_RESPONSE
    else:
        try:
            interaction_type = body.get("type")
            print(f"Interaction type: {interaction_type}")
            if interaction_type == DiscordInteractionType.APPLICATION_COMMAND:
                response = bot.process_bot_command(body, get_aws_services())
            elif interaction_type == DiscordInteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
                response = bot.process_input_autocomplete(body, get_aws_services())
            else:
                raise ValueError(f"Unsupported interaction type: {interaction_type}")
        except Exception as e:
            print(f"[lambda_handler] unhandled error: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            response = ResponseMessage.get_error_message().to_dict()

    print(f"Response: {response}")
    return response
