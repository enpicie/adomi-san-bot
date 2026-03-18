import re

from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
import commands.event.startgg.startgg_api as startgg_api
from commands.event.startgg.startgg_api import StartggAuthError
import database.dynamodb_utils as db_helper

_SCORE_PATTERN = re.compile(r"^(\d+)-(\d+)$")

_AUTH_REQUIRED_MSG = (
    "A start.gg organizer account must be linked to this server before scores can be reported. "
    "Contact an organizer to authenticate via `/startgg-connect`."
)
_AUTH_EXPIRED_MSG = (
    "The start.gg authentication for this server has expired or is no longer valid. "
    "Contact an organizer to re-authenticate via `/startgg-connect`."
)


def report_score(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")
    winner_id = event.get_command_input_value("winner")
    loser_id = event.get_command_input_value("loser")
    score_str: str = event.get_command_input_value("score")

    score_match = _SCORE_PATTERN.match(score_str.strip())
    if not score_match:
        return ResponseMessage(
            content="Invalid score format. Use `<winner score>-<loser score>`, e.g. `2-1`."
        )

    winner_games = int(score_match.group(1))
    loser_games = int(score_match.group(2))

    server_config = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(server_config, ResponseMessage):
        return server_config

    if not server_config.startgg_oauth_token:
        return ResponseMessage(content=_AUTH_REQUIRED_MSG)

    event_data = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data, ResponseMessage):
        return event_data

    if not event_data.startgg_url:
        return ResponseMessage(content="This event is not linked to a start.gg event.")

    registered = event_data.registered
    winner_info = registered.get(winner_id)
    loser_info = registered.get(loser_id)

    winner_name = winner_info.get("display_name") if winner_info else f"<@{winner_id}>"
    loser_name = loser_info.get("display_name") if loser_info else f"<@{loser_id}>"

    if not winner_info or not winner_info.get("external_id"):
        return ResponseMessage(
            content=f"**{winner_name}** is not linked to a start.gg account in this event. "
                    "They must be registered via start.gg to report scores."
        )

    if not loser_info or not loser_info.get("external_id"):
        return ResponseMessage(
            content=f"**{loser_name}** is not linked to a start.gg account in this event. "
                    "They must be registered via start.gg to report scores."
        )

    winner_entrant_id = winner_info["external_id"]
    loser_entrant_id = loser_info["external_id"]
    event_slug = startgg_api.extract_startgg_slug(event_data.startgg_url)

    result = startgg_api.find_set_between_players(
        event_slug, [winner_entrant_id, loser_entrant_id]
    )
    if result is None:
        return ResponseMessage(
            content=f"Could not find a set between **{winner_name}** and **{loser_name}** on start.gg."
        )

    set_id, entrant_ids, is_completed = result

    if is_completed:
        return ResponseMessage(
            content=(
                f"The set between **{winner_name}** and **{loser_name}** has already been reported on start.gg. "
                "No changes were made. Contact your organizer if there is an issue with the recorded result."
            )
        )

    game_data = []
    for game_num in range(1, winner_games + loser_games + 1):
        game_winner_id = winner_entrant_id if game_num <= winner_games else loser_entrant_id
        game_data.append({"winnerId": game_winner_id, "gameNum": game_num})

    try:
        startgg_api.report_set(set_id, entrant_ids[winner_entrant_id], game_data, server_config.startgg_oauth_token)
    except StartggAuthError:
        return ResponseMessage(content=_AUTH_EXPIRED_MSG)

    return ResponseMessage(
        content=f"Score reported on start.gg: <@{winner_id}> def. <@{loser_id}> ({score_str})"
    ).with_silent_pings()
