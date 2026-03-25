import json
import logging
import os

import boto3
import requests

import db
import discord

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REGION = os.environ["REGION"]
STARTGG_OAUTH_SECRET_NAME = os.environ["STARTGG_OAUTH_SECRET_NAME"]
OAUTH_REDIRECT_URI = os.environ["OAUTH_REDIRECT_URI"]

STARTGG_TOKEN_URL = "https://api.start.gg/oauth/access_token"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
secrets_client = boto3.client("secretsmanager", region_name=REGION)

_oauth_credentials: dict | None = None


def _get_oauth_credentials() -> dict:
    global _oauth_credentials
    if _oauth_credentials is None:
        response = secrets_client.get_secret_value(SecretId=STARTGG_OAUTH_SECRET_NAME)
        _oauth_credentials = json.loads(response["SecretString"])
    return _oauth_credentials


def _html_response(status_code: int, title: str, message: str) -> dict:
    color = "#2ecc71" if status_code == 200 else "#e74c3c"
    body = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        f"<title>{title}</title>"
        "<style>body{font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center}"
        f"h1{{color:{color}}}</style></head>"
        f"<body><h1>{title}</h1><p>{message}</p></body></html>"
    )
    return {"statusCode": status_code, "headers": {"Content-Type": "text/html"}, "body": body}


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    code = params.get("code")
    state = params.get("state")

    logger.info(f"[oauth:handler] Callback received — code_present={bool(code)}, state_present={bool(state)}, table={DYNAMODB_TABLE_NAME!r}")

    if not code or not state:
        logger.warning("OAuth callback missing code or state params")
        return _html_response(400, "Authorization Failed", "Missing required parameters. Please try connecting again.")

    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    state_data = db.consume_state(table, state)

    if not state_data:
        logger.warning(f"No valid state record for nonce: {state}")
        return _html_response(400, "Authorization Failed", "This link has expired or already been used. Please try connecting again.")

    discord_user_id = state_data["discord_user_id"]
    server_id = state_data.get("server_id")
    channel_id = state_data.get("channel_id")

    logger.info(f"[oauth:handler] Exchanging code for token — discord_user_id={discord_user_id!r}, server_id={server_id!r}")
    credentials = _get_oauth_credentials()
    token_response = requests.post(
        STARTGG_TOKEN_URL,
        json={
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": OAUTH_REDIRECT_URI,
        },
        timeout=10,
    )

    if not token_response.ok:
        logger.error(f"Token exchange failed: {token_response.status_code} {token_response.text}")
        return _html_response(500, "Authorization Failed", "Could not complete authorization with start.gg. Please try again.")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 7776000)  # start.gg default: 90 days

    if not access_token:
        logger.error(f"No access_token in token response: {token_data}")
        return _html_response(500, "Authorization Failed", "Could not retrieve access token. Please try again.")

    if server_id:
        db.update_server_oauth_token(table, server_id, access_token, refresh_token, expires_in)
        logger.info(f"[oauth:handler] Updated server OAuth token for server_id={server_id!r}")
        try:
            server_config = db.get_server_config(table, server_id)
            if server_config:
                discord.send_oauth_notification(server_config, discord_user_id)
        except Exception as e:
            logger.error(f"Failed to send OAuth notification for server {server_id}: {e}")
    else:
        logger.warning(f"No server_id in state for Discord user {discord_user_id}; server config not updated")

    if server_id and channel_id:
        return {
            "statusCode": 302,
            "headers": {"Location": f"https://discord.com/channels/{server_id}/{channel_id}"},
            "body": "",
        }
    return _html_response(200, "Connected!", "Your start.gg account has been linked to Discord. You can close this window.")
