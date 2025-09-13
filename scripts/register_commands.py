import sys
from pathlib import Path
import os
import requests

# --- Add src/ to sys.path so we can import command_map ---
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.append(str(SRC_DIR))

from commands.command_map import command_map

APP_ID = os.environ.get("DISCORD_APP_ID") # Repo Var
TOKEN = os.environ.get("DISCORD_BOT_TOKEN") # Repo Secret

if not TOKEN or not APP_ID:
    raise RuntimeError("DISCORD_BOT_TOKEN and DISCORD_APP_ID must be set as environment variables")

API_URL = f"https://discord.com/api/v10/applications/{APP_ID}/commands"


def build_command_payload(name: str, entry: dict) -> dict:
    payload = {
        "name": name,
        "description": entry["description"] or "No description",
        "type": 1,  # 1 = slash command
        "options": [],
    }

    for param in entry.get("params", []):
        payload["options"].append(
            {
                "name": param.name,
                "description": param.description or "No description",
                "type": param.type.value if hasattr(param.type, "value") else param.type,
                "required": param.required,
            }
        )

    return payload


def main():
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
    }

    failed_commands = []

    for name, entry in command_map.items():
        payload = build_command_payload(name, entry)
        response = requests.post(API_URL, headers=headers, json=payload)

        if response.status_code == 200 or response.status_code == 201:
            print(f"✅ Registered command: {name}")
        else:
            print(f"❌ Failed to register command: {name} ({response.status_code})")
            print(response.text)
            failed_commands.append(name)

    if failed_commands:
        raise RuntimeError(f"Failed to register commands: {', '.join(failed_commands)}")


if __name__ == "__main__":
    main()
