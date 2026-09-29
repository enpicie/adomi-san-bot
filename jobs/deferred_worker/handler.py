import json
import logging
import time

import worker_aws_client as aws_client
import discord_followup
import event_commands
import league_commands

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Mirrors adomin_messages.GENERAL_ERROR from the main bot
_GENERAL_ERROR = "🙀 AH! Something went wrong! Hang tight while I take a look. This might be a case for my supervisor `@enpicie`."

# Every command whose work cannot finish inside Discord's 3-second interaction
# deadline. The bot Lambda answers with a placeholder and enqueues here.
_COMMAND_HANDLERS = {
    "league-setup":             league_commands.handle_league_setup,
    "league-join":              league_commands.handle_league_join,
    "league-sync-participants": league_commands.handle_league_sync_participants,
    "league-deactivate":        league_commands.handle_league_deactivate,
    "league-report-score":      league_commands.handle_league_report_score,
    "event-create-startgg":     event_commands.handle_event_create_startgg,
}


def _process_record(payload: dict) -> None:
    command_name = payload["command_name"]
    event_body = payload["event_body"]
    application_id = event_body["application_id"]
    interaction_token = event_body["token"]

    enqueued_at = payload.get("enqueued_at")
    queue_age = f"{time.time() - enqueued_at:.1f}s" if enqueued_at else "unknown"
    logger.info(f"[deferred_worker] processing command={command_name!r} queue_age={queue_age}")

    handler_fn = _COMMAND_HANDLERS.get(command_name)
    if handler_fn is None:
        logger.warning(f"[deferred_worker] unknown command={command_name!r}")
        discord_followup.send_followup(application_id, interaction_token, f"❌ Unknown deferred command: `{command_name}`")
        return

    try:
        content = handler_fn(event_body, aws_client.get_aws_services())
    except Exception as e:
        logger.exception(f"[deferred_worker] unhandled error in {command_name!r}: {type(e).__name__}: {e}")
        content = _GENERAL_ERROR

    if isinstance(content, dict):
        discord_followup.send_followup(application_id, interaction_token, **content)
    else:
        discord_followup.send_followup(application_id, interaction_token, content)


def handler(event, context):
    """SQS-triggered Lambda: dispatches queued slash-command payloads to their
    handlers and posts the result as a Discord interaction followup."""
    for record in event["Records"]:
        payload = json.loads(record["body"])
        _process_record(payload)
