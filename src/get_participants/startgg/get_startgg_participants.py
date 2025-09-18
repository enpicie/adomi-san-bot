import os
from typing import List
import requests
from get_participants.models.participant import Participant

# Retrieve json dictionary that holds tournament name and participants
def get_event(tourneyURL: str) -> dict:

    url = "https://api.start.gg/gql/alpha"

    token = os.environ.get("STARTGG_API_TOKEN")
    # Parse the url string to request it so that it can be used in the query
    tourneyURL = tourneyURL.removeprefix("https://www.start.gg/")


    # These two variable are for start.gg request purposes

    headers = {
        "Authorization": f"Bearer {token}"
    }

    variables = {
        "slug": tourneyURL
    }

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
            #id
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
    response = requests.post(url=url, json={"query": body, "variables": variables}, headers=headers)
    results = response.json()

    # This event dictionary from the json file holds
    # The name for the tournament and the list of participants
    event_dict = results["data"]["event"]

    return event_dict

# return tournament name
def get_tourney(event_dict: dict) -> str:
    tourney_name = event_dict["tournament"]["name"]
    return tourney_name

# return list of participants
def get_participants(event_dict: dict) -> List[Participant]:
    
    # dictionary that holds list of participants
    participant_dict = event_dict["entrants"]["nodes"]

    # This list will hold participants (objects) based on the Participant class
    participants = []

    for item in participant_dict:
        participant_item = item["participants"][0]
        participant = Participant(participant_item["id"], participant_item["gamerTag"])

        discord_item = participant_item["user"]["authorizations"]

        # If they have a discord user linked to start.gg
        if discord_item is not None:
            participant.discord_id = discord_item[0]["externalId"]
            participant.discord_user = discord_item[0]["externalUsername"]
          
        participants.append(participant)

    return participants

# Returns string of list of participants
def output_list(tourney_name: str, participants: List[Participant]) -> str:
    ls = f"**{tourney_name}**\n"
    for i in range(len(participants)):
        ls += participants[i].tag
        if participants[i].discord_user is not None:
            ls += f"({participants[i].discord_user})"
        if i < len(participants) - 1:
            ls += "\n"
    
    return ls