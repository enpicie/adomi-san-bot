import time

_STATE_PK_PREFIX = "OAUTH_STATE#"
_STATE_SK = "STATE"
_USER_PK_PREFIX = "USER#"
_TOKEN_SK = "STARTGG_TOKEN"


def consume_state(table, nonce: str) -> dict | None:
    """Look up and delete the state nonce. Returns dict with discord_user_id and server_id, or None if not found."""
    pk = f"{_STATE_PK_PREFIX}{nonce}"
    response = table.get_item(Key={"PK": pk, "SK": _STATE_SK})
    item = response.get("Item")
    if not item:
        return None
    table.delete_item(Key={"PK": pk, "SK": _STATE_SK})
    return {"discord_user_id": item["discord_user_id"], "server_id": item.get("server_id")}


def store_user_tokens(table, discord_user_id: str, access_token: str, refresh_token: str, expires_in: int):
    table.put_item(Item={
        "PK": f"{_USER_PK_PREFIX}{discord_user_id}",
        "SK": _TOKEN_SK,
        "discord_user_id": discord_user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + expires_in,
    })


def get_server_config(table, server_id: str) -> dict | None:
    response = table.get_item(Key={"PK": f"SERVER#{server_id}", "SK": "CONFIG"})
    return response.get("Item")


def update_server_oauth_token(table, server_id: str, access_token: str):
    """Write the OAuth access token into the server's config record."""
    table.update_item(
        Key={"PK": f"SERVER#{server_id}", "SK": "CONFIG"},
        UpdateExpression="SET oauth_token_startgg = :token",
        ExpressionAttributeValues={":token": access_token},
    )
