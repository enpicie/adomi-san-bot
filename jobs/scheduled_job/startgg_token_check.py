import logging
import time

import db
import discord_api

logger = logging.getLogger()

_EXPIRY_WARNING_THRESHOLD_SECONDS = 24 * 60 * 60  # warn within 24 hours of expiry


def check_startgg_tokens(table):
    """Notify organizers when a server's start.gg OAuth token has expired or is about to.

    We do not attempt to refresh tokens automatically: the start.gg refresh endpoint reports
    success but the resulting access token still fails auth, so a refresh "success" is a false
    positive that leaves the bot broken. Instead, once a token is within the expiry window we
    tell organizers to re-link the account. The notification is sent once per expiry and re-arms
    automatically when a fresh token pushes the expiry back outside the window.
    """
    server_configs = db.get_all_server_configs_with_oauth(table)
    if not server_configs:
        logger.info("No servers with start.gg OAuth tokens, skipping token expiry check")
        return

    logger.info(f"Checking start.gg token expiry for {len(server_configs)} server(s)")

    for config in server_configs:
        server_id = config.get("server_id")
        expires_at = config.get("startgg_token_expires_at")

        if not expires_at:
            continue

        time_until_expiry = int(expires_at) - int(time.time())
        if time_until_expiry > _EXPIRY_WARNING_THRESHOLD_SECONDS:
            logger.info(f"Token for server {server_id} valid for {time_until_expiry}s, no notification needed")
            # Re-arm the notification if the token was re-linked since we last notified.
            if config.get("startgg_expiry_notified"):
                db.clear_startgg_expiry_notified(table, server_id)
                logger.info(f"Re-armed start.gg expiry notification for server {server_id}")
            continue

        if config.get("startgg_expiry_notified"):
            logger.info(f"Token for server {server_id} expiring/expired but organizers already notified, skipping")
            continue

        notification_channel_id = config.get("notification_channel_id")
        if not notification_channel_id:
            logger.info(f"No notification_channel_id for server {server_id}, cannot notify of start.gg token expiry")
            continue

        if time_until_expiry <= 0:
            status_line = "Adomin's start.gg authorization for this server has **expired**."
        else:
            status_line = "Adomin's start.gg authorization for this server will **expire soon**."

        logger.info(f"Token for server {server_id} expires in {time_until_expiry}s, notifying organizers")
        discord_api.send_organizer_notification(
            notification_channel_id,
            f"⚠️ {status_line} "
            "Start.gg score reporting will stop working until an organizer re-links the account "
            "via `/startgg-connect`.",
            organizer_role=config.get("organizer_role"),
            ping_organizers=config.get("ping_organizers", False),
        )
        db.mark_startgg_expiry_notified(table, server_id)
