from commands.models.command_mapping import CommandMapping
import commands.help.adomi_help_commands as adomi_help_commands

help_commands: CommandMapping = {
    "help": {
        "function": adomi_help_commands.give_help,
        "description": "Gives help on how Adomi-san works",
        "params": []
    },
    "help-check-in": {
        "function": adomi_help_commands.help_check_in,
        "description": "List all check-in commands with descriptions",
        "params": []
    },
    "help-register": {
        "function": adomi_help_commands.help_register,
        "description": "List all register commands with descriptions",
        "params": []
    },
    "help-event": {
        "function": adomi_help_commands.help_event,
        "description": "List all event commands with descriptions",
        "params": []
    }
}
