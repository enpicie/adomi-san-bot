import json
import logging
import os
import time

import boto3
import requests

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


# DynamoDB key constants
_STATE_PK_PREFIX = "OAUTH_STATE#"
_STATE_SK = "STATE"
_USER_PK_PREFIX = "USER#"
_TOKEN_SK = "STARTGG_TOKEN"


def _consume_state(table, nonce: str) -> str | None:
    """Look up and delete the state nonce. Returns discord_user_id or None if not found/expired."""
    pk = f"{_STATE_PK_PREFIX}{nonce}"
    response = table.get_item(Key={"PK": pk, "SK": _STATE_SK})
    item = response.get("Item")
    if not item:
        return None
    table.delete_item(Key={"PK": pk, "SK": _STATE_SK})
    return item["discord_user_id"]


def _store_user_tokens(table, discord_user_id: str, access_token: str, refresh_token: str, expires_in: int):
    table.put_item(Item={
        "PK": f"{_USER_PK_PREFIX}{discord_user_id}",
        "SK": _TOKEN_SK,
        "discord_user_id": discord_user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + expires_in,
    })


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

    if not code or not state:
        logger.warning("OAuth callback missing code or state params")
        return _html_response(400, "Authorization Failed", "Missing required parameters. Please try connecting again.")

    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    discord_user_id = _consume_state(table, state)

    if not discord_user_id:
        logger.warning(f"No valid state record for nonce: {state}")
        return _html_response(400, "Authorization Failed", "This link has expired or already been used. Please try connecting again.")

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

    _store_user_tokens(table, discord_user_id, access_token, refresh_token, expires_in)
    logger.info(f"Stored start.gg OAuth tokens for Discord user {discord_user_id}")

    return _html_response(200, "Connected!", "Your start.gg account has been linked to Discord. You can close this window.")
