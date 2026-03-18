import os

#######################################
# Environment Variables              #
#######################################
AWS_REGION = os.environ.get("REGION")
BOT_PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")
SQS_REMOVE_ROLE_QUEUE_URL = os.environ.get("REMOVE_ROLE_QUEUE_URL")
STARTGG_SECRET_NAME = os.environ.get("STARTGG_SECRET_NAME")

########################################
# Discord Data Constants              #
########################################
# Discord expects to see this response to its "ping pong" verification request
PING_PONG_RESPONSE = { "type": 1 }
