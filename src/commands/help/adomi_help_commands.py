from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from commands.check_in.mapping import checkin_commands
from commands.register.mapping import register_commands_mapping
from commands.event.mapping import event_commands_mapping
from commands.startgg.mapping import startgg_commands_mapping
from commands.league.mapping import league_commands_mapping

WIKI_LINK = "https://github.com/enpicie/adomi-san-bot/wiki/Adomi-is-here-to-help!"


def give_help(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    return ResponseMessage(
        content=(
            f"Adomi-san at your service! 🫡 You can call me Adomin!\n"
            f"Use `/check-in` to check in for events!\n"
            f"If you're an organizer, check [my wiki]({WIKI_LINK}) to see what commands you can use to get set up 🙇‍♀️"
        )
    ).with_suppressed_embeds()


def help_check_in(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    lines = ["**Check-in Commands**"]
    for name, entry in checkin_commands.items():
        lines.append(f"`/{name}` — {entry['description']}")
    return ResponseMessage(content="\n".join(lines))


def help_register(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    lines = ["**Register Commands**"]
    for name, entry in register_commands_mapping.items():
        lines.append(f"`/{name}` — {entry['description']}")
    return ResponseMessage(content="\n".join(lines))


def help_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    lines = ["**Event Commands**"]
    for name, entry in event_commands_mapping.items():
        lines.append(f"`/{name}` — {entry['description']}")
    return ResponseMessage(content="\n".join(lines))


def help_league(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    lines = ["**League Commands**"]
    for name, entry in league_commands_mapping.items():
        lines.append(f"`/{name}` — {entry['description']}")
    lines.append(
        "\n⚠️ **Note:** League commands that interact with Google Sheets require the sheet to be shared "
        "(with Editor access) to the bot's service account email. "
        "Use `/league-view` to see the configured service account address."
    )
    return ResponseMessage(content="\n".join(lines))


def help_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    lines = ["**start.gg Commands**"]
    for name, entry in startgg_commands_mapping.items():
        lines.append(f"`/{name}` — {entry['description']}")
    lines.append(
        "\n⚠️ **Note:** Participants must have their start.gg account linked to Discord "
        "for these commands to work as expected. "
        "This can be done in start.gg account settings under **Connections**."
    )
    return ResponseMessage(content="\n".join(lines))
