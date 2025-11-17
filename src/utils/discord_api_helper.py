import requests
import constants

BOT_AUTH_HEADERS = {
    "Authorization": f"Bot {constants.DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}

def add_role_to_user(guild_id: str, user_id: str, role_id: str) -> bool:
    """
    Adds a role to a Discord guild member using the Discord REST API.
    :return: True if successful (204 response), False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    headers = BOT_AUTH_HEADERS

    response = requests.put(url, headers=headers)

    if response.status_code == 204:
        return True
    else:
        print(
            f"Error adding role: status {response.status_code}, body: {response.text}"
        )
        return False


def remove_role_from_user(guild_id: str, user_id: str, role_id: str) -> bool:
    """
    Removes a role from a Discord guild member via Discord HTTP API.
    :return: True if successful (204), False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    headers = BOT_AUTH_HEADERS

    response = requests.delete(url, headers=headers)

    if response.status_code == 204:
        return True
    else:
        print(f"Error removing role: status {response.status_code}, body: {response.text}")
        return False
