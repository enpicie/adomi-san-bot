import os

# All env vars below are required: os.environ[...] raises KeyError at Lambda init
# if any are missing (intentional fail-fast, same strictness as before consolidation).
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REGION = os.environ["REGION"]
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
REMOVE_ROLE_QUEUE_URL = os.environ["REMOVE_ROLE_QUEUE_URL"]
