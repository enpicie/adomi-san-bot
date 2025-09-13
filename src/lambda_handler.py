import json

from discord import Message

import bot
import constants
import discord_auth_helper

def lambda_handler(event, context) -> Message:
    print(f"Received Event: {event}") # debug print

    # verify the signature
    try:
        discord_auth_helper.verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}")

    if not event["body"]:
        return { "message": "Request is not Lambda event: 'body-json' not found" }

    body = json.loads(event["body"])

    if discord_auth_helper.is_ping_pong(body):
        print("discord_auth_helper.is_ping_pong: True")
        response = constants.PING_PONG_RESPONSE
    else:
        data = body["data"]
        print(f"Received data: {data}") # debug print
        # TODO: implement bot logic here.
        response = bot.process_bot_command(data)

    print(f"Response: {response}") # debug print
    return response
