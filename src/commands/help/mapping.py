from commands.models.command_mapping import CommandMapping
import commands.help.adomi_help_commands as adomi_help_commands

help_commands: CommandMapping = {
    "help": {
        "function": adomi_help_commands.give_help,
        "description": "Gives help on how Adomi-san works",
        "params": []
    }
}
