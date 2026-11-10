import time
from typing import List, Optional, Tuple

from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import Table

import commands.queue.queue_constants as queue_constants
import utils.message_helper as message_helper
from database.models.event_data import EventData
from database.models.queue_entry import QueueEntry

_QUEUE = EventData.Keys.QUEUE


def _is_condition_failure(e: ClientError) -> bool:
    return e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def ensure_queue_map(table: Table, key: dict, event_data: EventData) -> None:
    """Creates the `queue` map on records missing it, since nested writes fail without it."""
    if event_data.queue is not None:
        return
    print(f"[queue] Initializing queue map for {key['SK']}")
    table.update_item(
        Key=key,
        UpdateExpression=f"SET {_QUEUE} = if_not_exists({_QUEUE}, :empty)",
        ExpressionAttributeValues={":empty": {}}
    )


def order_queue(queue: dict) -> List[Tuple[str, QueueEntry]]:
    """Returns (user_id, entry) oldest join first. Same-millisecond joins fall back to user_id."""
    entries = [(user_id, QueueEntry.from_dynamodb(record)) for user_id, record in queue.items()]
    entries.sort(key=lambda item: (item[1].joined_at, item[0]))
    return entries


def get_position(queue: dict, user_id: str) -> Optional[int]:
    """Returns the user's 1-based spot in the queue, or None if they are not in it."""
    for position, (queued_user_id, _) in enumerate(order_queue(queue), 1):
        if queued_user_id == user_id:
            return position
    return None


def join_queue(table: Table, key: dict, user_id: str, display_name: str) -> Optional[dict]:
    """Adds the user to the back of the queue.

    Returns the updated queue map, or None if the user was already in it.
    """
    entry = QueueEntry(display_name=display_name, joined_at=int(time.time() * 1000))
    try:
        response = table.update_item(
            Key=key,
            UpdateExpression=f"SET {_QUEUE}.#uid = :entry",
            ConditionExpression=f"attribute_not_exists({_QUEUE}.#uid)",
            ExpressionAttributeNames={"#uid": user_id},
            ExpressionAttributeValues={":entry": entry.to_dict()},
            ReturnValues="ALL_NEW"
        )
    except ClientError as e:
        if not _is_condition_failure(e):
            raise
        return None
    return response["Attributes"].get(_QUEUE, {})


def remove_from_queue(table: Table, key: dict, user_id: str) -> bool:
    """Drops the user from the queue. Returns False if they were not in it."""
    try:
        table.update_item(
            Key=key,
            UpdateExpression=f"REMOVE {_QUEUE}.#uid",
            ConditionExpression=f"attribute_exists({_QUEUE}.#uid)",
            ExpressionAttributeNames={"#uid": user_id}
        )
    except ClientError as e:
        if not _is_condition_failure(e):
            raise
        return False
    return True


def pop_queue(table: Table, key: dict, queue: dict, count: int) -> List[str]:
    """Removes up to `count` users from the front of the queue and returns their ids in order.

    Users already removed by a concurrent pop/leave are skipped, so no one is popped twice.
    """
    popped = []
    for user_id, _ in order_queue(queue):
        if len(popped) >= count:
            break
        if remove_from_queue(table, key, user_id):
            popped.append(user_id)
    return popped


def clear_queue(table: Table, key: dict) -> None:
    """Empties the queue."""
    table.update_item(
        Key=key,
        UpdateExpression=f"SET {_QUEUE} = :empty",
        ExpressionAttributeValues={":empty": {}}
    )


def build_queue_list(header: str, queue: dict) -> str:
    """Builds the numbered queue, oldest first, cut to fit one Discord message."""
    lines = [
        f"**{position}.** {message_helper.get_user_ping(user_id)}"
        for position, (user_id, _) in enumerate(order_queue(queue), 1)
    ]
    budget = queue_constants.QUEUE_CHAR_BUDGET - len(header) - 1
    return "\n".join([header] + message_helper.cap_lines(lines, budget))
