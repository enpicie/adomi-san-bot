import requests

# return tournament name
def get_tourney(node: str) -> str:
    tourney_name = node["tournament"]["name"]
    return tourney_name

class Player:
    def __init__(self, startgg_id, tag, discord_id = None, discord_user = None):
        self.startgg_id = startgg_id # ID in the start.gg bracket
        self.tag = tag # Gamer tag
        self.discord_id = discord_id # Discord ID
        self.discord_user = discord_user # Discord Username

def get_players(node):
    player_node = node["entrants"]["nodes"]

    players = []

    for item in player_node:
        player_item = item["participants"][0]
        player = Player(player_item["id"], player_item["gamerTag"])

        discord_item = player_item["user"]["authorization"]

        # If they have a discord user linked to start.gg
        if discord_item is not None:
            player.discord_id = discord_item[0]["externalId"]
            player.discord_user = discord_item[0]["externalUsername"]
          
        players.append(player)

    return players

# Retrieve json key that holds tournament name and players
def retPlayers(tourneyURL: str) -> str:

    url = "https://api.start.gg/gql/alpha"
	
    # Parse the url string to request it so that it can be used in the query
    tourneyURL = tourneyURL.removeprefix("https://www.start.gg/")

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

    return results["data"]["event"]

# Returns string of list of players
def output_list(tourney_name, players) -> str:
    ls = f"**{tourney_name}**\n"
    for i in range(len(players)):
        ls += players[i].tag
        if players[i].discord_user is not None:
            ls += f"({players[i].discord_user})"
        if i < len(players) - 1:
            ls += "\n"
    
    return ls