import os
from typing import List
import requests
from get_participants.models.participant import Participant

# Retrieve a dictionary that holds tournament name and participants
def get_event(tourney_url: str) -> dict:

    token = os.environ.get("STARTGG_API_TOKEN")

    # Parse the url string so that it can be used in the query
    tourney_url = tourney_url.removeprefix("https://www.start.gg/")

    # Startgg GraphQL endpoint for HTTP Requests
    endpoint = "https://api.start.gg/gql/alpha"

    # To pass the token to the API request
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # This is where graphql takes the tourney link as an input
    variables = {
        "slug": tourney_url
    }

    # To access start.gg
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
    
    # Startgg API request
    response = requests.post(url=endpoint, json={"query": body, "variables": variables}, headers=headers)
    results = response.json()

    # This event dictionary from the json file holds
    # The name for the tournament and the list of participants
    event_dict = results["data"]["event"]

    return event_dict


def get_tourney_name(event_dict: dict) -> str:
    tourney_name = event_dict["tournament"]["name"]
    return tourney_name


# Return list of participants
def get_participants(event_dict: dict) -> List[Participant]:
    
    # dictionary that holds list of start.gg attendees
    attendee_dict = event_dict["entrants"]["nodes"]

    participants = []

    # Loop through each participant (item) from the attendee dictionary 
    for item in attendee_dict:
        
        # participants is a list of length 1.  
        # So we need to access the first element to get the participant data
        participant_item = item["participants"][0] 

        participant = Participant(participant_item["id"], participant_item["gamerTag"])

        discord_item = participant_item["user"]["authorizations"]

        # If they have a discord account linked to start.gg
        if discord_item is not None:
            participant.discord_id = discord_item[0]["externalId"]
            participant.discord_user = discord_item[0]["externalUsername"]
          
        participants.append(participant)

    return participants

# Returns a string representation of list of participants
def participants_to_string(tourney_name: str, participants: List[Participant]) -> str:
    str_result = f"**{tourney_name}**\n"

    for i in range(len(participants)):
        str_result += participants[i].tag

        if participants[i].discord_user is not None:
            str_result += f"({participants[i].discord_user})"

        if i < len(participants) - 1:
            str_result += "\n"
    
    return str_result