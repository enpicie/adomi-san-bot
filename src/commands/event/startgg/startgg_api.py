import re
import boto3
import requests

import constants
import commands.event.startgg.startgg_graphql as startgg_graphql
from commands.event.startgg.models.startgg_event import StartggEvent

STARTGG_API_URL = "https://api.start.gg/gql/alpha"

_startgg_api_token: str | None = None

def _get_startgg_api_token() -> str:
    global _startgg_api_token
    if _startgg_api_token is None:
        client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
        response = client.get_secret_value(SecretId=constants.STARTGG_SECRET_NAME)
        _startgg_api_token = response["SecretString"]
    return _startgg_api_token

def is_valid_startgg_url(startgg_link: str) -> bool:
    startgg_pattern = re.compile(r"^https:\/\/www.start.gg\/tournament\/([^\/]+)\/event\/([^\/]+)$")
    return bool(re.fullmatch(startgg_pattern, startgg_link))

def query_startgg_event(tourney_url: str) -> StartggEvent:
    """
    Executes the start.gg GraphQL query and returns a populated StartggEvent object.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    request_body = {
        "query": startgg_graphql.EVENT_PARTICIPANTS_QUERY,
        "variables": {
            "slug": tourney_url.removeprefix("https://www.start.gg/")
        }
    }

    response = requests.post(
        url=STARTGG_API_URL,
        json=request_body,
        headers=headers,
        timeout=10
    )

    if not response.ok:
        print(f"Error querying start.gg: status {response.status_code}, body: {response.text}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"start.gg GraphQL errors for slug '{tourney_url}': {data['errors']}")

    return StartggEvent.from_dict(data["data"]["event"])
