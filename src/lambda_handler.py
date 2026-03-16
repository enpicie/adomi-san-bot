import json
import boto3

import bot
import constants
import utils.discord_auth_helper as auth_helper
from enums import DiscordInteractionType
from aws_services import AWSServices

dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)
sqs_resource = boto3.resource("sqs", region_name=constants.AWS_REGION)

aws_services = AWSServices(
    dynamodb_table=dynamodb.Table(constants.DYNAMODB_TABLE_NAME),
    remove_role_sqs_queue=sqs_resource.Queue(constants.SQS_REMOVE_ROLE_QUEUE_URL)
)

def lambda_handler(event, context):
    print(f"Received Event: {event}") # debug print

    # verify the signature
    try:
        auth_helper.verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}")

    if not event["body"]:
        return { "message": "Request is not Lambda event: 'body-json' not found" }

    body = json.loads(event["body"])

    if auth_helper.is_ping_pong(body):
        print("discord_auth_helper.is_ping_pong: True")
        response = constants.PING_PONG_RESPONSE
    else:
        print(f"Received data: {body}") # debug print
        interaction_type = body.get("type")
        print(f"Interaction type: {interaction_type}") # debug print
        if interaction_type == DiscordInteractionType.APPLICATION_COMMAND:
            response = bot.process_bot_command(body, aws_services)
        elif interaction_type == DiscordInteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            response = bot.process_input_autocomplete(body, aws_services)
        else:
            raise ValueError(f"Unsupported interaction type: {interaction_type}")

    print(f"Response: {response}") # debug print
    return response
