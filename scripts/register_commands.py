import sys
from pathlib import Path
import asyncio
import os

from discord import Client, Intents
from discord import app_commands

# --- Add src/ to sys.path so we can import command_map ---
ROOT_DIR = Path(__file__).resolve().parent.parent # root/
SRC_DIR = ROOT_DIR / "src"
sys.path.append(str(SRC_DIR))

from commands.command_map import command_map

TOKEN = os.environ.get("DISCORD_BOT_TOKEN") # GitHub Actions secret

intents = Intents.default()
bot = Client(intents=intents)
tree = app_commands.CommandTree(bot)


async def register_all_commands():
    for name, entry in command_map.items():
        params = entry["params"]

        async def callback(interaction, **kwargs):
            # Call the original function with kwargs as a dict
            result = await entry["function"](kwargs)
            await interaction.response.send_message(
                result.content if hasattr(result, "content") else str(result)
            )

        command = app_commands.Command(
            name=name,
            description=entry["description"],
            callback=callback,
            parameters=params,
        )
        tree.add_command(command)

    # Register globally
    await tree.sync()
    print("All commands registered globally.")


async def main():
    await bot.login(TOKEN)
    await register_all_commands()
    await bot.close() # exit immediately after registering


if __name__ == "__main__":
    asyncio.run(main())
