import re
import secrets
import time

import constants
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
import commands.event.startgg.startgg_api as startgg_api
from commands.event.startgg.startgg_api import StartggAuthError, StartggPermissionError
import database.dynamodb_utils as db_helper
from database.models.oauth_state import OAuthState
import utils.message_helper as message_helper
import utils.permissions_helper as permissions_helper

_SCORE_PATTERN = re.compile(r"^(\d+)-(\d+)$")

_STARTGG_OAUTH_BASE_URL = "https://start.gg/oauth/authorize"

_AUTH_REQUIRED_MSG = (
    "A start.gg organizer account must be linked to this server before scores can be reported. "
    "Contact an organizer to authenticate via `/startgg-connect`."
)
_AUTH_EXPIRED_MSG = (
    "The start.gg authentication for this server has expired or is no longer valid. "
    "Contact an organizer to re-authenticate via `/startgg-connect`."
)


def _parse_score(score_str: str) -> tuple[int, int] | None:
    """Parses a '<winner>-<loser>' score string into (winner_games, loser_games), or None if invalid."""
    score_match = _SCORE_PATTERN.match(score_str.strip())
    if not score_match:
        return None
    return int(score_match.group(1)), int(score_match.group(2))


def build_set_game_data(winner_games: int, loser_games: int, winner_entrant_id, loser_entrant_id) -> list[dict]:
    """Builds the per-game start.gg gameData list: the winner takes games 1..winner_games, the loser the rest."""
    game_data = []
    for game_num in range(1, winner_games + loser_games + 1):
        game_winner_id = winner_entrant_id if game_num <= winner_games else loser_entrant_id
        game_data.append({"winnerId": game_winner_id, "gameNum": game_num})
    return game_data


def _validate_reportable_player(player_info: dict | None, player_name: str) -> ResponseMessage | None:
    """Returns an error ResponseMessage if the player is missing or has no start.gg entrant ID, else None."""
    if not player_info:
        return ResponseMessage(
            content=f"**{player_name}** is not registered for this event. "
                    "If they are registered on start.gg, they need to link their Discord account on their start.gg profile, "
                    "then an organizer can refresh with `/event-refresh-startgg`."
        )
    if not player_info.get("external_id"):
        return ResponseMessage(
            content=f"**{player_name}** does not have a start.gg entrant ID. "
                    "Their Discord account was not linked on start.gg when the event was last imported. "
                    "Have them link their Discord on start.gg, then an organizer can refresh with `/event-refresh-startgg`."
        )
    return None


def startgg_connect(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Generates a start.gg OAuth link so an organizer can connect their account to this server."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    client_id = constants.STARTGG_OAUTH_CLIENT_ID
    redirect_uri = constants.STARTGG_OAUTH_REDIRECT_URI
    if not client_id or not redirect_uri:
        return ResponseMessage(content="😔 start.gg OAuth is not configured for this bot. Contact the bot administrator.")

    nonce = secrets.token_urlsafe(32)
    server_id = event.get_server_id()
    discord_user_id = event.get_user_id()

    pk = f"{OAuthState.Keys.PK_PREFIX}{nonce}"
    print(f"[startgg] Writing OAuth state — PK={pk!r}, table={aws_services.dynamodb_table.name!r}, server_id={server_id!r}, discord_user_id={discord_user_id!r}")
    aws_services.dynamodb_table.put_item(Item={
        "PK": pk,
        "SK": OAuthState.Keys.SK,
        OAuthState.Keys.DISCORD_USER_ID: discord_user_id,
        OAuthState.Keys.SERVER_ID: server_id,
        OAuthState.Keys.CHANNEL_ID: event.get_channel_id(),
        OAuthState.Keys.EXPIRES_AT: int(time.time()) + OAuthState.Keys.TTL_SECONDS,
    })
    print(f"[startgg] OAuth state written successfully — PK={pk!r}")

    oauth_url = (
        f"{_STARTGG_OAUTH_BASE_URL}"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&scope=user.identity+tournament.manager+tournament.reporter"
        f"&redirect_uri={redirect_uri}"
        f"&state={nonce}"
    )

    return ResponseMessage(
        content=(
            f"🔗 Click this [start.gg OAuth Link]({oauth_url}) to connect your start.gg account to this server.\n\n"
            f"*This link expires in 10 minutes. Once authorized, scores can be reported via `/startgg-report-score`.*"
            " Only one organizer needs to connect their start.gg account to enable reporting in this server."
        )
    ).with_suppressed_embeds()


def notify_unlinked(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists start.gg participants for an event who have not linked Discord on their profile. Organizer only."""
    error_message = permissions_helper.verify_has_organizer_role(event, aws_services)
    if error_message:
        return error_message

    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")

    event_data = db_helper.get_server_event_data_or_fail(server_id, event_id, aws_services.dynamodb_table)
    if isinstance(event_data, ResponseMessage):
        return event_data

    if not event_data.startgg_url:
        return ResponseMessage(content="❌ This event is not linked to a start.gg event.")

    try:
        startgg_event = startgg_api.query_startgg_event(event_data.startgg_url)
    except Exception as e:
        print(f"[startgg] notify_unlinked: error querying event: {e}")
        return ResponseMessage(content="❌ Failed to fetch participant data from start.gg. Check the event link and try again.")

    lines = []
    for participant in startgg_event.no_discord_participants:
        lines.append(f"- {participant.display_name}")

    if not lines:
        return ResponseMessage(content="✅ All start.gg participants have Discord linked on their profile.")

    return ResponseMessage(
        content=(
            f"⚠️ **{len(lines)} participant(s) do not have Discord linked on start.gg:**\n"
            + "\n".join(lines)
            + "\n\nTo link Discord: go to your start.gg profile → **Edit Profile** → **Connections** → connect Discord "
            "and ensure **Display on profile** is enabled."
            + "\nScore reporting requires start.gg and Discord to be linked correctly."
        )
    )


def report_score(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Reports a set result (or DQ) between two registered players to start.gg."""
    server_id = event.get_server_id()
    event_id = event.get_command_input_value("event_name")
    winner_id = event.get_command_input_value("winner")
    loser_id = event.get_command_input_value("loser")
    score_str: str = event.get_command_input_value("score")

    is_dq = score_str.strip().lower() == "dq"
    if is_dq:
        winner_games = 0
        loser_games = 0
    else:
        parsed_score = _parse_score(score_str)
        if parsed_score is None:
            return ResponseMessage(
                content="Invalid score format. Use `<winner score>-<loser score>`, e.g. `2-1`, or `dq`."
            )
        winner_games, loser_games = parsed_score

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

    winner_name = winner_info.get("display_name") if winner_info else message_helper.get_user_ping(winner_id)
    loser_name = loser_info.get("display_name") if loser_info else message_helper.get_user_ping(loser_id)

    winner_error = _validate_reportable_player(winner_info, winner_name)
    if winner_error:
        return winner_error

    loser_error = _validate_reportable_player(loser_info, loser_name)
    if loser_error:
        return loser_error

    winner_entrant_id = winner_info["external_id"]
    loser_entrant_id = loser_info["external_id"]
    event_slug = startgg_api.extract_startgg_slug(event_data.startgg_url)

    result = startgg_api.find_set_between_players(
        event_slug, [winner_entrant_id, loser_entrant_id]
    )
    if result is None:
        return ResponseMessage(
            content=f"Could not find an open set between **{winner_name}** and **{loser_name}** on start.gg. "
                    "The set may not have been called yet, or these players are not matched in the current bracket."
        )

    set_id, entrant_ids, is_completed = result

    if is_completed:
        return ResponseMessage(
            content=(
                f"The set between **{winner_name}** and **{loser_name}** has already been reported on start.gg. "
                "No changes were made. Contact your organizer if there is an issue with the recorded result."
            )
        )

    game_data = [] if is_dq else build_set_game_data(winner_games, loser_games, winner_entrant_id, loser_entrant_id)

    try:
        startgg_api.report_set(set_id, entrant_ids[winner_entrant_id], game_data, server_config.startgg_oauth_token, is_dq=is_dq)
    except StartggAuthError:
        return ResponseMessage(content=_AUTH_EXPIRED_MSG)
    except StartggPermissionError:
        return ResponseMessage(
            content=(
                "❌ The connected start.gg account does not have permission to report scores for this tournament. "
                "The account must be an organizer or TO for the event on start.gg. "
                "Contact an organizer to re-authenticate via `/startgg-connect` using the correct account."
            )
        )
    except ValueError as e:
        return ResponseMessage(content=f"❌ {e}")

    result_str = f"{message_helper.get_user_ping(loser_id)} DQ" if is_dq else score_str
    return ResponseMessage(
        content=f"Score reported on start.gg: {message_helper.get_user_ping(winner_id)} def. {message_helper.get_user_ping(loser_id)} ({result_str})"
    ).with_silent_pings()
