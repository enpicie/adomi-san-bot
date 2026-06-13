import logging
import time

logger = logging.getLogger()

_STATE_PK_PREFIX = "OAUTH_STATE#"
_STATE_SK = "STATE"
_PK_SERVER_PREFIX = "SERVER#"
_SK_CONFIG = "CONFIG"


def consume_state(table, nonce: str) -> dict | None:
    """Look up and delete the state nonce. Returns dict with discord_user_id and server_id, or None if not found/expired."""
    pk = f"{_STATE_PK_PREFIX}{nonce}"
    # Truncate the nonce in logs — it is a live credential until consumed.
    pk_preview = f"{_STATE_PK_PREFIX}{nonce[:8]}…"
    logger.info(f"[oauth:db] Looking up state record: PK={pk_preview!r}, table={table.name!r}")
    # Atomic consume: delete and read the old item in a single call so a nonce
    # can only ever be used once, even under concurrent requests.
    response = table.delete_item(Key={"PK": pk, "SK": _STATE_SK}, ReturnValues="ALL_OLD")
    item = response.get("Attributes")
    if not item:
        logger.warning(f"[oauth:db] State record not found for PK={pk!r}")
        return None
    expires_at = item.get("expires_at", 0)
    if expires_at and int(time.time()) > expires_at:
        logger.warning(f"[oauth:db] State record expired (expires_at={expires_at}, now={int(time.time())})")
        return None
    logger.info(f"[oauth:db] State record found — discord_user_id={item.get('discord_user_id')!r}, server_id={item.get('server_id')!r}")
    return {"discord_user_id": item["discord_user_id"], "server_id": item.get("server_id"), "channel_id": item.get("channel_id")}


def get_server_config(table, server_id: str) -> dict | None:
    """Get the server CONFIG record. Returns item dict or None."""
    response = table.get_item(Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": _SK_CONFIG})
    return response.get("Item")


def update_server_oauth_token(table, server_id: str, access_token: str, refresh_token: str, expires_in: int):
    """Write the OAuth access token, refresh token, and expiry into the server's config record."""
    table.update_item(
        Key={"PK": f"{_PK_SERVER_PREFIX}{server_id}", "SK": _SK_CONFIG},
        UpdateExpression=(
            "SET oauth_token_startgg = :token, "
            "startgg_refresh_token = :refresh_token, "
            "startgg_token_expires_at = :expires_at"
        ),
        ExpressionAttributeValues={
            ":token": access_token,
            ":refresh_token": refresh_token,
            ":expires_at": int(time.time()) + expires_in,
        },
    )
