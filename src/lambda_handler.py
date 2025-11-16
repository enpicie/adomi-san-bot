import json
import boto3
from mypy_boto3_dynamodb.service_resource import Table

import bot
import constants
import utils.discord_auth_helper as auth_helper

dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)
table: Table = dynamodb.Table(constants.DYNAMODB_TABLE_NAME)

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
        response = bot.process_bot_command(body, table)

    print(f"Response: {response}") # debug print
    return response
