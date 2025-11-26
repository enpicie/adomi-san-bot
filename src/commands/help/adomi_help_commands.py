
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

WIKI_LINK = "https://github.com/enpicie/adomi-san-bot/wiki/Adomi-is-here-to-help!"

def give_help(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    return ResponseMessage(
        content=(
            f"Use `/check-in` to check in for events!\n"
            f"If you're an organizer, check [my wiki]({WIKI_LINK}) to see what commands you can use to get set up 🙇‍♀️"
        )
    )
