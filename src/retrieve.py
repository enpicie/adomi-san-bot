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
