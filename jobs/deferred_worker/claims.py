# MIRROR: src/database/claims.py — keep in sync (independent Lambda packaging prevents imports).
# Differs from src only in logging (logger, not print) and the Table type annotation.
"""Single-use claims backed by DynamoDB conditional writes.

An organizer whose first attempt looked like it failed re-runs the command, and
SQS delivers at least once, so the same creation can arrive twice. A duplicate
check that reads before it writes cannot see a create still in flight.

A claim is a conditional put on a key that identifies the work. The first caller
wins; anyone else is a repeat. A claim guards only the in-flight window of one
create: the winner releases it once its create attempt finishes, success or
failure, and find_duplicate_event stops any repeat after that.

Claims also carry an `expires_at` TTL, but DynamoDB sweeps expired items only
"typically within a few days", and until then they still show in reads and
writes. The conditional put therefore checks `expires_at` itself, so a claim
left behind by a crashed invocation can be retaken as soon as it expires rather
than whenever the sweep runs.

Claims fail open: an unavailable table degrades to the previous behaviour rather
than blocking every command.
"""
import logging
import time

from botocore.exceptions import ClientError

logger = logging.getLogger()

PK_EVENT_CREATE_PREFIX = "EVENTCREATE#"
SK_CLAIM = "CLAIM"
EXPIRES_AT_ATTR = "expires_at"

# Winners release their claim when the create finishes, so this only bounds how
# long a claim left by an invocation that died mid-create blocks a retry. It
# must outlast one create (Discord API call plus DynamoDB write).
EVENT_CREATE_TTL_SECONDS = 120


def build_event_create_pk(server_id: str, event_identity: str) -> str:
    """Build the DynamoDB partition key value for an in-flight event creation."""
    return f"{PK_EVENT_CREATE_PREFIX}{server_id}#{event_identity}"


# Taken if no claim exists, or if the one that exists has expired but has not
# been swept yet.
CLAIM_CONDITION = f"attribute_not_exists(PK) OR {EXPIRES_AT_ATTR} < :now"


def _try_claim(pk: str, table, ttl_seconds: int, label: str) -> bool:
    """Conditionally put a claim record, returning True only if this caller won it."""
    now = int(time.time())
    try:
        table.put_item(
            Item={
                "PK": pk,
                "SK": SK_CLAIM,
                EXPIRES_AT_ATTR: now + ttl_seconds,
            },
            ConditionExpression=CLAIM_CONDITION,
            ExpressionAttributeValues={":now": now},
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info(f"[claims] DUPLICATE {label} pk={pk} already claimed")
            return False
        logger.warning(f"[claims] claim failed open {label} pk={pk} error={e.response.get('Error', {}).get('Code')}")
        return True
    except Exception as e:
        # Connection/timeout errors are not ClientError. Claims run before the
        # work they guard, so anything other than a lost claim must fail open or
        # a DynamoDB blip would take the whole bot down.
        logger.warning(f"[claims] claim failed open {label} pk={pk} error={type(e).__name__}")
        return True


def try_claim_event_create(server_id: str, event_identity: str, table) -> bool:
    """Attempt to claim the creation of one specific event.

    Guards the window that a read-then-write duplicate check cannot: two
    invocations that both read "no duplicate" before either has written.

    :param server_id: Discord server the event would belong to.
    :param event_identity: Stable identity of the event being created — the
                           start.gg slug where there is one, else name + start time.
    :param table: The DynamoDB table holding claims.
    :return: True if this caller may create the event, False if an identical
             creation is already in flight.
    """
    if not event_identity:
        logger.info(f"[claims] no event identity for server={server_id}, skipping claim")
        return True
    return _try_claim(
        build_event_create_pk(server_id, event_identity), table, EVENT_CREATE_TTL_SECONDS, "event-create"
    )


def release_event_create_claim(server_id: str, event_identity: str, table) -> None:
    """Release a claim this caller won, once its create attempt has finished.

    Call only after try_claim_event_create returned True, and always in a
    `finally`: releasing a claim this caller lost would delete another
    invocation's claim. Fails open — a claim that cannot be deleted still
    expires after EVENT_CREATE_TTL_SECONDS.
    """
    if not event_identity:
        return
    pk = build_event_create_pk(server_id, event_identity)
    try:
        table.delete_item(Key={"PK": pk, "SK": SK_CLAIM})
    except Exception as e:
        logger.warning(f"[claims] release failed open event-create pk={pk} error={type(e).__name__}")
