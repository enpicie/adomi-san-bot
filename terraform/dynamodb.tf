resource "aws_dynamodb_table" "adomi_discord_server_table" {
  # Shorten app name for brevity in DynamoDB table name
  name      = "adomi-discord-server-data-${var.deployment_env}"
  hash_key  = "PK" # Will be Discord Server ID as "SERVER#<server_id>"
  range_key = "SK" # Will be sort key as "CONFIG" or "CHANNEL#<channel_id>"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}
