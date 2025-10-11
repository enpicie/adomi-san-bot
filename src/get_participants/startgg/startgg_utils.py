import os
from typing import List
import requests
from get_participants.startgg.models.startgg_participant import StartggParticipant

def get_event(tourney_url: str) -> dict:

    token = os.environ.get("STARTGG_API_TOKEN")

    tourney_url = tourney_url.removeprefix("https://www.start.gg/")

    endpoint = "https://api.start.gg/gql/alpha"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    variables = {
        "slug": tourney_url
    }

    # This query will only list a total of 75 players to accommodates discords 2000 character limit
    body = """
    query EventEntrants($slug: String) {
      event(slug: $slug) {
        id
        tournament {name}
        name
        entrants(query: {
          page: 1
          perPage: 75
        }) {
          pageInfo {
            total
          }
          nodes {
            participants {
              id
              gamerTag
              user {
                authorizations(types:DISCORD) {
                  externalId
                  externalUsername
                }
              }
            }
          }
        }
      }
    }
    """
    
    response = requests.post(url=endpoint, json={"query": body, "variables": variables}, headers=headers)
    results = response.json()

    event_dict = results["data"]["event"]

    return event_dict

def get_tourney_name(event_dict: dict) -> str:
    tourney_name = event_dict["tournament"]["name"]
    return tourney_name

def get_participants(event_dict: dict) -> List[StartggParticipant]:
    
    attendee_dict = event_dict["entrants"]["nodes"]

    participants = []

    for entrant in attendee_dict:
        
        # participants is a list of length 1. 
        participant_data = entrant["participants"][0] 

        participant = StartggParticipant(participant_data["id"], participant_data["gamerTag"])

        discord_item = participant_data["user"]["authorizations"]

        if discord_item is not None:
            participant.discord_id = discord_item[0]["externalId"]
            participant.discord_user = discord_item[0]["externalUsername"]
          
        participants.append(participant)

    return participants

def participants_to_string(tourney_name: str, participants: List[StartggParticipant]) -> str:
    str_result = f"**{tourney_name}**\n"

    for i in range(len(participants)):
        str_result += participants[i].tag

        if participants[i].discord_user is not None:
            str_result += f"({participants[i].discord_user})"

        if i < len(participants) - 1:
            str_result += "\n"
    
    return str_result
