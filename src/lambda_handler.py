import json
import traceback

import bot
import constants
import utils.discord_auth_helper as auth_helper
import utils.permissions_helper as permissions_helper
from aws_client import get_aws_services
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from enums import DiscordInteractionType, DiscordCallbackType

# Commands whose full processing is handled by the sheets_agent Lambda.
# The main bot immediately acknowledges and enqueues; the agent sends the real followup.
_SHEETS_COMMANDS = {
    "league-setup",
    "league-join",
    "league-sync-participants",
    "league-deactivate",
    "league-report-score",
}

_SHEETS_COMMAND_ACK = {
    "league-setup":              "⏳ Setting up the Participants sheet...",
    "league-join":               "⏳ Adding you to the league...",
    "league-sync-participants":  "⏳ Syncing participants from the sheet... This may take a few minutes for larger leagues.",
    "league-deactivate":         "⏳ Updating your participant status...",
    "league-report-score":       "⏳ Reporting score...",
}


def _dispatch_to_sheets_agent(body: dict, command_name: str) -> None:
    payload = json.dumps({"command_name": command_name, "event_body": body})
    get_aws_services().sheets_agent_sqs_queue.send_message(MessageBody=payload)
    print(f"[lambda_handler] dispatched command={command_name!r} to sheets_agent queue")


def _sheets_ack_response(command_name: str) -> dict:
    content = _SHEETS_COMMAND_ACK.get(command_name, "⏳ Your request has been queued...")
    return {
        "type": DiscordCallbackType.MESSAGE_WITH_SOURCE,
        "data": {"content": content},
    }


def lambda_handler(event, context):
    print(f"Received Event: {event}")

    # verify the signature
    try:
        auth_helper.verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}") from e

    if not event["body"]:
        return { "message": "Request is not Lambda event: 'body-json' not found" }

    body = json.loads(event["body"])

    if auth_helper.is_ping_pong(body):
        print("discord_auth_helper.is_ping_pong: True")
        response = constants.PING_PONG_RESPONSE
    else:
        try:
            interaction_type = body.get("type")
            print(f"Interaction type: {interaction_type}")
            if interaction_type == DiscordInteractionType.APPLICATION_COMMAND:
                command_name = body.get("data", {}).get("name", "")
                if command_name in _SHEETS_COMMANDS:
                    if command_name == "league-deactivate":
                        options = body.get("data", {}).get("options", [])
                        if any(o["name"] == "player" for o in options):
                            error = permissions_helper.verify_has_organizer_role(DiscordEvent(body), get_aws_services())
                            if error:
                                return {
                                    "type": DiscordCallbackType.MESSAGE_WITH_SOURCE,
                                    "data": {"content": "🙅‍♀️ Only organizers can deactivate other players. To deactivate yourself, call `/league-deactivate` without the `player` parameter."},
                                }
                    _dispatch_to_sheets_agent(body, command_name)
                    response = _sheets_ack_response(command_name)
                else:
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
