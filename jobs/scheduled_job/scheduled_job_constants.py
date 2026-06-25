import os

import boto3

# All env vars below are required: os.environ[...] raises KeyError at Lambda init
# if any are missing (intentional fail-fast, same strictness as before consolidation).
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REGION = os.environ["REGION"]
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ["DISCORD_BOT_TOKEN_SECRET_NAME"]
REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
STARTGG_SECRET_NAME = os.environ["STARTGG_SECRET_NAME"]

_discord_bot_token = None
_startgg_api_token = None
_secretsmanager_client = None


def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager", region_name=REGION)
    return _secretsmanager_client


def get_discord_bot_token() -> str:
    """Fetches and caches the Discord bot token from Secrets Manager (once per cold start)."""
    global _discord_bot_token
    if _discord_bot_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=DISCORD_BOT_TOKEN_SECRET_NAME)
        _discord_bot_token = response["SecretString"]
    return _discord_bot_token


def get_startgg_api_token() -> str:
    """Fetches and caches the start.gg API token from Secrets Manager (once per cold start).

    MIRROR: src/commands/event/startgg/startgg_api.py _get_startgg_api_token — keep in sync.
    """
    global _startgg_api_token
    if _startgg_api_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=STARTGG_SECRET_NAME)
        _startgg_api_token = response["SecretString"]
    return _startgg_api_token
