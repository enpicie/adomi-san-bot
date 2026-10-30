import commands.score.score_constants as score_constants
import commands.score.score_helper as score_helper
import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.score_entry import ScoreEntry

RETRY_MESSAGE = "⚠️ I couldn't update your score because it changed at the same moment. Please try again."


def _get_event_or_fail(event: DiscordEvent, aws_services: AWSServices) -> tuple[EventData, dict] | ResponseMessage:
    """Returns the command's event and its DynamoDB key, or the lookup's error message."""
    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    key = db_helper.build_event_key(server_id, event_data_result.event_id or event_id)
    return event_data_result, key


def _get_open_event_or_fail(event: DiscordEvent, aws_services: AWSServices) -> tuple[EventData, dict] | ResponseMessage:
    """Same as _get_event_or_fail, but also fails while the scoreboard is closed."""
    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result

    event_data, _ = result
    if not event_data.score_enabled:
        return ResponseMessage(
            content=f"😵‍💫 Scores are not being accepted right now for **{event_data.event_name}**.\n"
                    "An Organizer must open the scoreboard before scores can be reported."
        )
    return result


def _get_amount_or_fail(event: DiscordEvent) -> int | ResponseMessage:
    """Returns the `amount` input (default 1), or an error message if it is below 1."""
    amount = event.get_command_input_value("amount")
    if amount is None:
        return score_constants.DEFAULT_AMOUNT
    if amount < 1:
        return ResponseMessage(content="⚠️ Amount must be at least 1.")
    return amount


def _get_score_or_fail(event: DiscordEvent) -> int | ResponseMessage:
    """Returns the `score` input, or an error message if it is negative."""
    score = event.get_command_input_value("score")
    if score < 0:
        return ResponseMessage(content="⚠️ Score can't be negative.")
    return score


def score_add(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Adds to the calling user's score for an event, putting them on the scoreboard if needed."""
    amount = _get_amount_or_fail(event)
    if isinstance(amount, ResponseMessage):
        return amount

    result = _get_open_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_user_id()
    table = aws_services.dynamodb_table
    score_helper.ensure_scores_map(table, key, event_data)
    new_score = score_helper.add_score(table, key, user_id, event.get_username(), amount)
    if new_score is None:
        return ResponseMessage(content=RETRY_MESSAGE)

    print(f"[score] ADD user={user_id} amount={amount} new_score={new_score} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Added **{amount}**! Your score for **{event_data.event_name}** is now **{new_score}**."
    )


def score_deduct(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Subtracts from the calling user's score for an event. Never goes below 0."""
    amount = _get_amount_or_fail(event)
    if isinstance(amount, ResponseMessage):
        return amount

    result = _get_open_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_user_id()
    scores = event_data.scores or {}
    if user_id not in scores:
        return ResponseMessage(
            content=f"🧐 You don't have a score for **{event_data.event_name}** yet."
        )

    new_score = score_helper.deduct_score(aws_services.dynamodb_table, key, user_id, event.get_username(), amount)
    if new_score is None:
        current_score = ScoreEntry.from_dynamodb(scores[user_id]).score
        return ResponseMessage(
            content=f"⚠️ Can't deduct **{amount}**: your score is **{current_score}** and can't go below 0."
        )

    print(f"[score] DEDUCT user={user_id} amount={amount} new_score={new_score} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Deducted **{amount}**. Your score for **{event_data.event_name}** is now **{new_score}**."
    )


def score_set(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the calling user's score for an event to an exact value."""
    score = _get_score_or_fail(event)
    if isinstance(score, ResponseMessage):
        return score

    result = _get_open_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_user_id()
    table = aws_services.dynamodb_table
    score_helper.ensure_scores_map(table, key, event_data)
    score_helper.set_score(table, key, user_id, event.get_username(), score)

    print(f"[score] SET user={user_id} score={score} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Your score for **{event_data.event_name}** is now **{score}**."
    )


def score_view(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Shows the calling user's score and rank for an event."""
    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, _ = result

    ranking = score_helper.get_rank(event_data.scores or {}, event.get_user_id())
    if ranking is None:
        return ResponseMessage(
            content=f"🧐 You don't have a score for **{event_data.event_name}** yet."
        )

    rank, entry = ranking
    return ResponseMessage(
        content=f"🏅 You're **#{rank}** on **{event_data.event_name}** with a score of **{entry.score}**."
    )


def show_scoreboard(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Shows every score for an event, highest first."""
    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, _ = result

    scores = event_data.scores or {}
    if not scores:
        return ResponseMessage(content=f"🧐 There are no scores yet for **{event_data.event_name}**.")

    content = score_helper.build_scoreboard(f"🏆 **{event_data.event_name} Scoreboard**", scores)
    return ResponseMessage(content=content).with_silent_pings()


def toggle_scoreboard(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Opens or closes player score reporting for an event based on the 'state' input. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    _, key = result

    score_state = event.get_command_input_value("state")
    should_enable = score_state == score_constants.START_PARAM
    print(f"[score] {EventData.Keys.SCORE_ENABLED}: {should_enable} via input {score_state}")

    aws_services.dynamodb_table.update_item(
        Key=key,
        UpdateExpression=f"SET {EventData.Keys.SCORE_ENABLED} = :enable",
        ExpressionAttributeValues={":enable": should_enable}
    )

    content = (
        "🟢 Scoreboard open! Players can report scores with `/score-add`, `/score-deduct`, and `/score-set`"
        if should_enable
        else "🔴 Scoreboard closed! Players can no longer change their scores."
    )
    return ResponseMessage(content=content)


def reset_scoreboard(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Clears every score for an event. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    if not event_data.scores:
        return ResponseMessage(content="🧐 There are no scores to clear.")

    score_helper.reset_scores(aws_services.dynamodb_table, key)
    print(f"[score] RESET {key['SK']}")
    return ResponseMessage(content=f"✅ The scoreboard for **{event_data.event_name}** has been reset.")


def score_override(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets another user's score for an event to an exact value. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    score = _get_score_or_fail(event)
    if isinstance(score, ResponseMessage):
        return score

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_command_input_value("user")
    resolved_users = event.event_body.get("data", {}).get("resolved", {}).get("users", {})
    resolved_user = resolved_users.get(user_id, {})
    display_name = resolved_user.get("global_name") or resolved_user.get("username") or user_id

    table = aws_services.dynamodb_table
    score_helper.ensure_scores_map(table, key, event_data)
    score_helper.set_score(table, key, user_id, display_name, score)

    print(f"[score] OVERRIDE user={user_id} score={score} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Set {message_helper.get_user_ping(user_id)}'s score for **{event_data.event_name}** to **{score}**."
    ).with_silent_pings()


def score_remove(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Removes a user from an event's scoreboard. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    result = _get_event_or_fail(event, aws_services)
    if isinstance(result, ResponseMessage):
        return result
    event_data, key = result

    user_id = event.get_command_input_value("user")
    if user_id not in (event_data.scores or {}):
        return ResponseMessage(
            content=f"⚠️ {message_helper.get_user_ping(user_id)} has no score for this event."
        ).with_silent_pings()

    score_helper.remove_score(aws_services.dynamodb_table, key, user_id)
    print(f"[score] REMOVE user={user_id} {key['SK']}")
    return ResponseMessage(
        content=f"✅ Removed {message_helper.get_user_ping(user_id)} from the scoreboard."
    ).with_silent_pings()
