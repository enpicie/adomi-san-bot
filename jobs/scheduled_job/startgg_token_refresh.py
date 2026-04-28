import json
import logging
import os
import time

import boto3
import requests

import db
import discord_api

logger = logging.getLogger()

_STARTGG_OAUTH_SECRET_NAME = os.environ["STARTGG_OAUTH_SECRET_NAME"]
_REGION = os.environ["REGION"]
_REFRESH_THRESHOLD_SECONDS = 24 * 60 * 60  # 24 hours
_STARTGG_REFRESH_URL = "https://api.start.gg/oauth/refresh"

_secrets_client = boto3.client("secretsmanager", region_name=_REGION)
_oauth_credentials: dict | None = None


def _get_oauth_credentials() -> dict:
    global _oauth_credentials
    if _oauth_credentials is None:
        response = _secrets_client.get_secret_value(SecretId=_STARTGG_OAUTH_SECRET_NAME)
        _oauth_credentials = json.loads(response["SecretString"])
    return _oauth_credentials


def refresh_startgg_tokens(table):
    """Check all servers with start.gg OAuth tokens and refresh any expiring within 24 hours."""
    server_configs = db.get_all_server_configs_with_oauth(table)
    if not server_configs:
        logger.info("No servers with start.gg OAuth tokens, skipping token refresh")
        return

    logger.info(f"Checking start.gg token refresh for {len(server_configs)} server(s)")

    try:
        credentials = _get_oauth_credentials()
    except Exception as e:
        logger.error(f"Failed to load start.gg OAuth credentials from Secrets Manager: {e}")
        return

    for config in server_configs:
        server_id = config.get("server_id")
        refresh_token = config.get("startgg_refresh_token")
        expires_at = config.get("startgg_token_expires_at")

        if not refresh_token or not expires_at:
            continue

        time_until_expiry = int(expires_at) - int(time.time())
        if time_until_expiry > _REFRESH_THRESHOLD_SECONDS:
            logger.info(f"Token for server {server_id} valid for {time_until_expiry}s, no refresh needed")
            continue

        logger.info(f"Token for server {server_id} expires in {time_until_expiry}s, refreshing")
        try:
            response = requests.post(
                _STARTGG_REFRESH_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "scope": "user.identity tournament.manager",
                },
                timeout=10,
            )
            logger.info(f"Token refresh response for server {server_id}: {response.status_code} {response.text}")

            if not response.ok:
                logger.error(f"Token refresh failed for server {server_id}: {response.status_code} {response.text}")
                notification_channel_id = config.get("notification_channel_id")
                if notification_channel_id:
                    organizer_role = config.get("organizer_role")
                    discord_api.send_organizer_notification(
                        notification_channel_id,
                        "⚠️ Adomin failed to refresh the start.gg OAuth token for this server. "
                        "Start.gg score reporting may stop working soon. "
                        "An organizer may need to re-link the start.gg account.",
                        organizer_role=organizer_role,
                        ping_organizers=bool(organizer_role),
                    )
                continue

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            new_expires_in = token_data.get("expires_in", 7 * 24 * 3600)

            if not new_access_token:
                logger.error(f"No access_token in refresh response for server {server_id}: {token_data}")
                continue

            new_expires_at = int(time.time()) + new_expires_in
            db.update_server_oauth_token(table, server_id, new_access_token, new_refresh_token, new_expires_at)
            logger.info(f"Refreshed start.gg OAuth token for server {server_id}, expires_at={new_expires_at}")

            notification_channel_id = config.get("notification_channel_id")
            if notification_channel_id:
                discord_api.send_organizer_notification(
                    notification_channel_id,
                    "✅ Adomin successfully refreshed the start.gg OAuth token for this server. "
                    "Score reporting continues to work normally.",
                )

        except Exception as e:
            logger.error(f"Exception during token refresh for server {server_id}: {e}")
            notification_channel_id = config.get("notification_channel_id")
            if notification_channel_id:
                organizer_role = config.get("organizer_role")
                discord_api.send_organizer_notification(
                    notification_channel_id,
                    "⚠️ Adomin encountered an unexpected error while refreshing the start.gg OAuth token for this server. "
                    "Start.gg score reporting may stop working soon. "
                    "An organizer may need to re-link the start.gg account.",
                    organizer_role=organizer_role,
                    ping_organizers=bool(organizer_role),
                )
