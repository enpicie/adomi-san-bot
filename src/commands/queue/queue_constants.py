# Re-exports the shared Start/End toggle values — check_in_constants is the single definition.
import commands.check_in.check_in_constants as check_in_constants

START_PARAM = check_in_constants.START_PARAM
END_PARAM = check_in_constants.END_PARAM

DEFAULT_POP_COUNT = 1
MAX_POP_COUNT = 10

QUEUE_CHAR_BUDGET = 1900  # Discord rejects messages over 2000
