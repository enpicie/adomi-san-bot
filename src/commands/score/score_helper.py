from typing import List, Optional, Tuple

from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import Table

import commands.score.score_constants as score_constants
import utils.message_helper as message_helper
from database.models.event_data import EventData
from database.models.score_entry import ScoreEntry

_SCORES = EventData.Keys.SCORES
_ENTRY_SCORE = f"{_SCORES}.#uid.{ScoreEntry.Keys.SCORE}"
_ENTRY_NAME = f"{_SCORES}.#uid.{ScoreEntry.Keys.DISPLAY_NAME}"
_FOOTER_RESERVE = len("\n…and 9999 more")


def _is_condition_failure(e: ClientError) -> bool:
    return e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def ensure_scores_map(table: Table, key: dict, event_data: EventData) -> None:
    """Creates the `scores` map on events that predate scoreboards, since nested writes fail without it."""
    if event_data.scores is not None:
        return
    print(f"[score] Initializing scores map for {key['SK']}")
    table.update_item(
        Key=key,
        UpdateExpression=f"SET {_SCORES} = if_not_exists({_SCORES}, :empty)",
        ExpressionAttributeValues={":empty": {}}
    )


def _increment(table: Table, key: dict, user_id: str, display_name: str, delta: int) -> int:
    """Adds `delta` to an existing entry. Raises a condition failure if the entry is missing."""
    response = table.update_item(
        Key=key,
        UpdateExpression=f"SET {_ENTRY_SCORE} = {_ENTRY_SCORE} + :delta, {_ENTRY_NAME} = :name",
        ConditionExpression=f"attribute_exists({_SCORES}.#uid)",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":delta": delta, ":name": display_name},
        ReturnValues="UPDATED_NEW"
    )
    return int(response["Attributes"][_SCORES][user_id][ScoreEntry.Keys.SCORE])


def change_score(table: Table, key: dict, user_id: str, display_name: str, delta: int) -> Optional[int]:
    """Adds `delta` (negative to deduct) to the user's score, creating their entry if needed.

    Returns None if a concurrent write won twice.
    """
    try:
        return _increment(table, key, user_id, display_name, delta)
    except ClientError as e:
        if not _is_condition_failure(e):
            raise

    try:
        table.update_item(
            Key=key,
            UpdateExpression=f"SET {_SCORES}.#uid = :entry",
            ConditionExpression=f"attribute_not_exists({_SCORES}.#uid)",
            ExpressionAttributeNames={"#uid": user_id},
            ExpressionAttributeValues={":entry": ScoreEntry(display_name=display_name, score=delta).to_dict()}
        )
        return delta
    except ClientError as e:
        if not _is_condition_failure(e):
            raise

    try:
        return _increment(table, key, user_id, display_name, delta)
    except ClientError as e:
        if not _is_condition_failure(e):
            raise
        print(f"[score] Score change lost a write race twice for user {user_id} on {key['SK']}")
        return None


def set_score(table: Table, key: dict, user_id: str, display_name: str, score: int) -> None:
    """Sets the user's score to an absolute value, creating the entry if needed."""
    table.update_item(
        Key=key,
        UpdateExpression=f"SET {_SCORES}.#uid = :entry",
        ExpressionAttributeNames={"#uid": user_id},
        ExpressionAttributeValues={":entry": ScoreEntry(display_name=display_name, score=score).to_dict()}
    )


def remove_score(table: Table, key: dict, user_id: str) -> None:
    """Drops the user's entry from the scoreboard."""
    table.update_item(
        Key=key,
        UpdateExpression=f"REMOVE {_SCORES}.#uid",
        ExpressionAttributeNames={"#uid": user_id}
    )


def reset_scores(table: Table, key: dict) -> None:
    """Clears every entry from the scoreboard."""
    table.update_item(
        Key=key,
        UpdateExpression=f"SET {_SCORES} = :empty",
        ExpressionAttributeValues={":empty": {}}
    )


def rank_scores(scores: dict) -> List[Tuple[int, str, ScoreEntry]]:
    """Returns (rank, user_id, entry) sorted by score descending. Ties share a rank (1, 1, 3)."""
    entries = [(user_id, ScoreEntry.from_dynamodb(record)) for user_id, record in scores.items()]
    entries.sort(key=lambda item: (-item[1].score, item[1].display_name.lower()))

    ranked = []
    for position, (user_id, entry) in enumerate(entries, 1):
        if ranked and ranked[-1][2].score == entry.score:
            rank = ranked[-1][0]
        else:
            rank = position
        ranked.append((rank, user_id, entry))
    return ranked


def get_rank(scores: dict, user_id: str) -> Optional[Tuple[int, ScoreEntry]]:
    """Returns (rank, entry) for the user, or None if they have no entry."""
    for rank, ranked_user_id, entry in rank_scores(scores):
        if ranked_user_id == user_id:
            return rank, entry
    return None


def build_scoreboard(header: str, scores: dict) -> str:
    """Builds the scoreboard text, cut at the row cap (never mid-tie) or the character budget."""
    ranked = rank_scores(scores)
    lines = [header]
    length = len(header)
    shown = 0
    for rank, user_id, entry in ranked:
        past_row_cap = shown >= score_constants.SCOREBOARD_MAX_ROWS and rank != ranked[shown - 1][0]
        line = f"**{rank}.** {message_helper.get_user_ping(user_id)} - **{entry.score}**"
        if past_row_cap or length + len(line) + 1 > score_constants.SCOREBOARD_CHAR_BUDGET - _FOOTER_RESERVE:
            break
        lines.append(line)
        length += len(line) + 1
        shown += 1

    remaining = len(ranked) - shown
    if remaining:
        lines.append(f"…and {remaining} more")
    return "\n".join(lines)
