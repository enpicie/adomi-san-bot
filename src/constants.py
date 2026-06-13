import os

#######################################
# Environment Variables              #
#######################################
AWS_REGION = os.environ.get("REGION")
BOT_PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")
SQS_REMOVE_ROLE_QUEUE_URL = os.environ.get("REMOVE_ROLE_QUEUE_URL")
SQS_SHEETS_AGENT_QUEUE_URL = os.environ.get("SHEETS_AGENT_QUEUE_URL")
STARTGG_SECRET_NAME = os.environ.get("STARTGG_SECRET_NAME")
STARTGG_OAUTH_CLIENT_ID = os.environ.get("STARTGG_OAUTH_CLIENT_ID")
STARTGG_OAUTH_REDIRECT_URI = os.environ.get("STARTGG_OAUTH_REDIRECT_URI")
GOOGLE_SHEETS_SECRET_NAME = os.environ.get("GOOGLE_SHEETS_SECRET_NAME")
GOOGLE_SERVICE_ACCOUNT_EMAIL = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")

########################################
# Discord Data Constants              #
########################################
# Discord expects to see this response to its "ping pong" verification request
PING_PONG_RESPONSE = { "type": 1 }
