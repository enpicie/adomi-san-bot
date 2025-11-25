import database.dynamodb_utils as db_helper
from database.models.event_data import EventData
import utils.permissions_helper as permissions_helper
import commands.get_registered.startgg.startgg_api as startgg_api
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def get_registered_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    error_message = permissions_helper.require_organizer_role(event)
    if isinstance(error_message, ResponseMessage):
          return error_message

    event_url = event.get_command_input_value("event_link")
    if not startgg_api.is_valid_startgg_url(event_url):
         return ResponseMessage(
              content="😖 Sorry! This start.gg event link is not valid."
                      "Make sure it is a link to an event in a tournament like this: "
                      "https://www.start.gg/tournament/midweek-melting/event/mbaacc-double-elim"
         )

    startgg_event = startgg_api.query_startgg_event(event_url)
    participants_count = len(startgg_event.participants)
    no_discord_names = [p.display_name for p in startgg_event.no_discord_participants]
    if participants_count == 0 and len(no_discord_names) == 0:
        return ResponseMessage(
            content="😔 No registered participants found for this start.gg event"
        )

    if startgg_event.participants:
        startgg_participants_data = {
            participant.user_id: participant.to_dict()
            for participant in startgg_event.participants
        }
        aws_services.dynamodb_table.update_item(
            Key={"PK": db_helper.build_server_pk(event.get_server_id()), "SK": EventData.Keys.SK_SERVER},
            UpdateExpression=f"SET {EventData.Keys.REGISTERED} = :startgg_registered",
            ExpressionAttributeValues={":startgg_registered": startgg_participants_data}
        )

    if no_discord_names:
        participant_list_markdown = "\n".join([f"* {name}" for name in no_discord_names])
        no_discord_report = (
            "\n**I found these start.gg users do not have Discord linked**\n"
            "---\n"
            f"{participant_list_markdown}"
        )
    else:
        no_discord_report = ""

    return ResponseMessage(
        content=f"👍 Found {participants_count} participants registered in start.gg!" + no_discord_report
    )
