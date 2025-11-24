resource "aws_dynamodb_table" "adomi_discord_server_table" {
  # Shorten app name for brevity in DynamoDB table name
  name         = "adomi-discord-server-data-${var.deployment_env}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK" # Will be Discord Server ID as "SERVER#<server_id>"
  range_key    = "SK" # Will be sort key as "CONFIG" or "CHANNEL#<channel_id>" or "SERVER"

  # Other attributes used by the bot:
  # checked_in: map of user_id -> {username, check_in_time}
  #   - This attribute is created dynamically by the bot; no need to declare it here.

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}
