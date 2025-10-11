from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import constants

# Discord uses "ping pong" message to verify bot.
def is_ping_pong(body: dict) -> bool:
    if body["type"]:
        # Look up type for "pong" response to Discord's ping reques.
        return body["type"] == constants.DISCORD_CALLBACK_TYPES["PONG"]

# Discord needs to verify bot application.
def verify_signature(event: dict):
    event_body = event["body"]
    verify_key = VerifyKey(bytes.fromhex(constants.BOT_PUBLIC_KEY))
    # Expected headers from Discord verification request.
    auth_sig = event["headers"].get("x-signature-ed25519")
    auth_ts  = event["headers"].get("x-signature-timestamp")

    try:
        verify_key.verify(f"{auth_ts}{event_body}".encode(), bytes.fromhex(auth_sig))
    except BadSignatureError:
        raise Exception("Verification failed")
