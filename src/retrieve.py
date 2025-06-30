import requests

# Player class
class Player:
    def __init__(self, partID, tag, discID = None, discUser = None):
        self.partID = partID # ID in the start.gg bracket
        self.tag = tag # Gamer tag
        self.discID = discID # Discord ID
        self.discUser = discUser # Discord Username

# Retrieve players that are part of the event
def retPlayers(tourneyURL):

    url = "https://api.start.gg/gql/alpha"
	
    # Parse the url string to request it so that it can be used in the query
    tourneyURL = tourneyURL[21:]

    # Replace with any start.gg API token that you want
    token = ""

    headers = {
        "Authorization": "Bearer {token}".format(token = token)
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
          perPage: 50
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
    
    # API request
    response = requests.post(url=url, json={"query": body, "variables": variables}, headers=headers)
    results = response.json()

    # Retrieve name of the tournament
    tourneyName = results["data"]["event"]["tournament"]["name"]
    
    # Create player list
    players = []
    node = results["data"]["event"]["entrants"]["nodes"]

    # Create a player object for each participant
    # and add them to the list
    for item in node:
        partItem = item["participants"][0]
        player = Player(partItem["id"], partItem["gamerTag"])
        discordItem = partItem["user"]["authorizations"]

        # If they do not have a discord user linked to start.gg
        if discordItem is not None: 
            player.discID = discordItem[0]["externalId"]
            player.discUser = discordItem[0]["externalUsername"]
        
        players.append(player)

    # Return tournament name and list of players
    return tourneyName, players

# Returns a vertical list of players
# as a string
def outList(tourneyName, players):
    ls = f"**{tourneyName}**\n"
    for i in range(len(players)):
        ls += players[i].tag
        if players[i].discUser is not None:
            ls += f"({players[i].discUser})"
        if i < len(players) - 1:
            ls += "\n"
    
    return ls