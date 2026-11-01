# Re-exports the shared Start/End toggle values — check_in_constants is the single definition.
import commands.check_in.check_in_constants as check_in_constants

START_PARAM = check_in_constants.START_PARAM
END_PARAM = check_in_constants.END_PARAM

DEFAULT_AMOUNT = 1

SCOREBOARD_MAX_ROWS = 40
SCOREBOARD_CHAR_BUDGET = 1900  # Discord rejects messages over 2000
