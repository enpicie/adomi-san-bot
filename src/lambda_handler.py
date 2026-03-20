import json
import boto3

import bot
import constants
import utils.discord_auth_helper as auth_helper
from enums import DiscordInteractionType, DiscordCallbackType
from aws_services import AWSServices

dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)
sqs_resource = boto3.resource("sqs", region_name=constants.AWS_REGION)

aws_services = AWSServices(
    dynamodb_table=dynamodb.Table(constants.DYNAMODB_TABLE_NAME),
    remove_role_sqs_queue=sqs_resource.Queue(constants.SQS_REMOVE_ROLE_QUEUE_URL),
    sheets_agent_sqs_queue=sqs_resource.Queue(constants.SQS_SHEETS_AGENT_QUEUE_URL),
)

# Commands whose full processing is handled by the sheets_agent Lambda.
# The main bot immediately acknowledges and enqueues; the agent sends the real followup.
_SHEETS_COMMANDS = {
    "league-setup",
    "league-join",
    "league-sync-participants",
}

_SHEETS_COMMAND_ACK = {
    "league-setup":              "⏳ Setting up the Participants sheet...",
    "league-join":               "⏳ Adding you to the league...",
    "league-sync-participants":  "⏳ Syncing participants from the sheet...",
}


def _dispatch_to_sheets_agent(body: dict, command_name: str) -> None:
    payload = json.dumps({"command_name": command_name, "event_body": body})
    aws_services.sheets_agent_sqs_queue.send_message(MessageBody=payload)
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
        interaction_type = body.get("type")
        print(f"Interaction type: {interaction_type}")
        if interaction_type == DiscordInteractionType.APPLICATION_COMMAND:
            command_name = body.get("data", {}).get("name", "")
            if command_name in _SHEETS_COMMANDS:
                _dispatch_to_sheets_agent(body, command_name)
                response = _sheets_ack_response(command_name)
            else:
                response = bot.process_bot_command(body, aws_services)
        elif interaction_type == DiscordInteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            response = bot.process_input_autocomplete(body, aws_services)
        else:
            raise ValueError(f"Unsupported interaction type: {interaction_type}")

    print(f"Response: {response}")
    return response
