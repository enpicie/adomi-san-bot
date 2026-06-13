import os

# All env vars below are required: os.environ[...] raises KeyError at Lambda init
# if any are missing (intentional fail-fast, same strictness as before consolidation).
DYNAMODB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
REGION = os.environ["REGION"]
STARTGG_OAUTH_SECRET_NAME = os.environ["STARTGG_OAUTH_SECRET_NAME"]
OAUTH_REDIRECT_URI = os.environ["OAUTH_REDIRECT_URI"]
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
