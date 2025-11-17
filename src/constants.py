import os

#######################################
# Environment Variables              #
#######################################
AWS_REGION = os.environ.get("REGION")
BOT_PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
STARTGG_API_TOKEN = os.environ.get("STARTGG_API_TOKEN")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")

########################################
# Discord Data Constants              #
########################################
# Discord expects to see this response to its "ping pong" verification request
PING_PONG_RESPONSE = { "type": 1 }
# Discord defined message types
DISCORD_CALLBACK_TYPES =  {
    "PONG": 1,
    "MESSAGE_WITH_SOURCE": 4, # CHANNEL_MESSAGE_WITH_SOURCE but omitting CHANNEL for brevity in refs
    "DEFERRED_MESSAGE_WITH_SOURCE": 5,
    "DEFERRED_UPDATE_MESSAGE": 6, # only for component interactions
    "UPDATE_MESSAGE": 7,
    "APPLICATION_COMMAND_AUTOCOMPLETE_RESULT": 8,
    "MODAL": 9
}

########################################
# DynamoDB Constants                  #
########################################
PK_SERVER_PREFIX = "SERVER#"
SK_CONFIG = "CONFIG"
SK_SERVER = "SERVER"
SK_CHANNEL_PREFIX = "CHANNEL#"
