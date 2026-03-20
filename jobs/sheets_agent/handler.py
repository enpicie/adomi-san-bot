import json

from aws_client import get_aws_services
from discord_followup import send_followup
import league_commands

_COMMAND_HANDLERS = {
    "league-setup":             league_commands.handle_league_setup,
    "league-join":              league_commands.handle_league_join,
    "league-sync-participants": league_commands.handle_league_sync_participants,
}


def _process_record(payload: dict) -> None:
    command_name = payload["command_name"]
    event_body = payload["event_body"]
    application_id = event_body["application_id"]
    interaction_token = event_body["token"]

    print(f"[sheets_agent] processing command={command_name!r}")

    handler_fn = _COMMAND_HANDLERS.get(command_name)
    if handler_fn is None:
        print(f"[sheets_agent] unknown command={command_name!r}")
        send_followup(application_id, interaction_token, f"❌ Unknown sheets command: `{command_name}`")
        return

    try:
        content = handler_fn(event_body, get_aws_services())
    except Exception as e:
        print(f"[sheets_agent] unhandled error in {command_name!r}: {type(e).__name__}: {e}")
        content = "❌ An unexpected error occurred. Please try again."

    send_followup(application_id, interaction_token, content)


def handler(event, context):
    for record in event["Records"]:
        payload = json.loads(record["body"])
        _process_record(payload)
