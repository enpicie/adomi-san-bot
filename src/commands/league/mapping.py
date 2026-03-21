from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.league.league_commands as league_commands
from commands.league.autocomplete_handlers import LEAGUE_NAME_PARAM

LEAGUE_ID_PARAM = CommandParam(
    name="league_id",
    description="Unique league identifier (max 4 characters)",
    param_type=AppCommandOptionType.string,
    required=True,
    choices=None
)

ACTIVE_PARTICIPANT_ROLE_PARAM = CommandParam(
    name="active_participant_role",
    description="Role to assign to active league participants",
    param_type=AppCommandOptionType.role,
    required=False,
    choices=None
)

league_commands_mapping: CommandMapping = {
    "league-create": {
        "function": league_commands.create_league,
        "description": "Create a new league tracked via Google Sheets",
        "params": [
            CommandParam(
                name="league_name",
                description="Name of the league",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            LEAGUE_ID_PARAM,
            CommandParam(
                name="google_sheets_link",
                description="Link to the Google Sheet tracking this league",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            ACTIVE_PARTICIPANT_ROLE_PARAM,
        ]
    },
    "league-update": {
        "function": league_commands.update_league,
        "description": "Update an existing league's details",
        "params": [
            LEAGUE_NAME_PARAM,
            CommandParam(
                name="new_name",
                description="New name for the league",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="google_sheets_link",
                description="New Google Sheets link for the league",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            ACTIVE_PARTICIPANT_ROLE_PARAM,
        ]
    },
    "league-list": {
        "function": league_commands.list_leagues,
        "description": "List all leagues for this server",
        "params": []
    },
    "league-view": {
        "function": league_commands.view_league,
        "description": "View details of an existing league",
        "params": [LEAGUE_NAME_PARAM]
    },
    "league-setup": {
        "function": league_commands.setup_league,
        "description": "Initialize the Participants sheet in the league's linked Google Sheet",
        "params": [LEAGUE_NAME_PARAM]
    },
    "league-delete": {
        "function": league_commands.delete_league,
        "description": "Delete a league record",
        "params": [LEAGUE_NAME_PARAM]
    },
    "league-join": {
        "function": league_commands.join_league,
        "description": "Join a league — adds you to the league's participant sheet",
        "params": [LEAGUE_NAME_PARAM]
    },
    "league-join-toggle": {
        "function": league_commands.toggle_join_league,
        "description": "Toggle whether joining is enabled for a league",
        "params": [
            LEAGUE_NAME_PARAM,
            CommandParam(
                name="state",
                description="Set to 'Start' to open joining, and set to 'End' to close joining",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(name="Start", value="Start"),
                    ParamChoice(name="End", value="End")
                ]
            )
        ]
    },
    "league-sync-participants": {
        "function": league_commands.sync_active_participants,
        "description": "Sync participants from the league's Google Sheet, assigning/removing the active participant role",
        "params": [LEAGUE_NAME_PARAM]
    },
    "league-deactivate": {
        "function": league_commands.deactivate_league_participant,
        "description": "Mark yourself (or another player) as inactive in a league's participant sheet",
        "params": [
            LEAGUE_NAME_PARAM,
            CommandParam(
                name="dnf",
                description="Set to True to mark as DNF instead of Inactive",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=None
            ),
            CommandParam(
                name="player",
                description="(Organizers only) The player to deactivate",
                param_type=AppCommandOptionType.user,
                required=False,
                choices=None
            ),
        ]
    },
}
