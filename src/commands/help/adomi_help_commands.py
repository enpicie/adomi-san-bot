from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from commands.check_in.mapping import checkin_commands
from commands.register.mapping import register_commands_mapping
from commands.event.mapping import event_commands_mapping
from commands.startgg.mapping import startgg_commands_mapping
from commands.league.mapping import league_commands_mapping
from commands.schedule.mapping import schedule_commands_mapping

WIKI_LINK = "https://github.com/enpicie/adomi-san-bot/wiki/Adomi-is-here-to-help!"


def _build_help_lines(header: str, mapping: dict, footer: str | None = None) -> str:
    """Builds a help message: a header, one `/command — description` line per mapping entry, and an optional footer."""
    lines = [header]
    for name, entry in mapping.items():
        lines.append(f"`/{name}` — {entry['description']}")
    if footer:
        lines.append(footer)
    return "\n".join(lines)


def give_help(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Returns the general introduction message with a link to the bot's wiki."""
    return ResponseMessage(
        content=(
            f"Adomi-san at your service! 🫡 You can call me Adomin!\n"
            f"Use `/check-in` to check in for events!\n"
            f"If you're an organizer, check [my wiki]({WIKI_LINK}) to see what commands you can use to get set up 🙇‍♀️"
        )
    ).with_suppressed_embeds()


def help_check_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all check-in commands with their descriptions."""
    return ResponseMessage(content=_build_help_lines("**Check-in Commands**", checkin_commands))


def help_register(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all register commands with their descriptions."""
    return ResponseMessage(content=_build_help_lines("**Register Commands**", register_commands_mapping))


def help_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all event commands with their descriptions."""
    return ResponseMessage(content=_build_help_lines("**Event Commands**", event_commands_mapping))


def help_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all league commands with their descriptions, plus the Google Sheets sharing note."""
    return ResponseMessage(content=_build_help_lines(
        "**League Commands**",
        league_commands_mapping,
        footer=(
            "\n⚠️ **Note:** League commands that interact with Google Sheets require the sheet to be shared "
            "(with Editor access) to the bot's service account email. "
            "Use `/league-view` to see the configured service account address."
        )
    ))


def help_schedule(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all schedule commands with their descriptions, plus the planned-event tip."""
    return ResponseMessage(content=_build_help_lines(
        "**Schedule Commands**",
        schedule_commands_mapping,
        footer=(
            "\n💡 **Tip:** Use `/schedule-plan-event` to add a placeholder for an event before creating it. "
            "When you run `/event-create` with the same name, the placeholder is removed automatically."
        )
    ))


def help_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Lists all start.gg commands with their descriptions, plus the Discord-linking note."""
    return ResponseMessage(content=_build_help_lines(
        "**start.gg Commands**",
        startgg_commands_mapping,
        footer=(
            "\n⚠️ **Note:** Participants must have their start.gg account linked to Discord "
            "for these commands to work as expected. "
            "This can be done in start.gg account settings under **Connections**."
        )
    ))
