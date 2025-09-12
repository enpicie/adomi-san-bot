import constants
import discord_helper

def lambda_handler(event, context):
    print(f"event {event}") # debug print

    # verify the signature
    try:
        discord_helper.verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}")

    if not event["body"]:
        return { "message": "Request is not Lambda event: 'body-json' not found" }

    body = event["body"]

    if discord_helper.is_ping_pong(body):
        print("is_ping_pong: True")
        response = constants.PING_PONG
    else:
        data = body["data"]
        print(f"data: {data}") # debug print

    print(f"response: {response}") # debug print
    return response
