import json
import requests
import time
import os

TOKEN = os.environ["DISCORD_BOT_TOKEN"]

def discord_delete(url):
    while True:
        r = requests.delete(url, headers={"Authorization": f"Bot {TOKEN}"})
        if r.status_code != 429:
            return r
        time.sleep(r.json().get("retry_after", 1))


def handler(event, context):
    for record in event["Records"]:
        payload = json.loads(record["body"])

        guild_id = payload["guild_id"]
        user_id  = payload["user_id"]
        role_id  = payload["role_id"]

        url = (
            f"https://discord.com/api/v10/"
            f"guilds/{guild_id}/members/{user_id}/roles/{role_id}"
        )

        resp = discord_delete(url)
        if resp.status_code not in (204, 200):
            raise Exception(f"Failed to remove role: {resp.status_code} {resp.text}")
