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

  attribute {
    name = "server_id"
    type = "S"
  }

  attribute {
    name = "event_name"
    type = "S"
  }

  attribute {
    name = "league_name"
    type = "S"
  }

  global_secondary_index {
    name = "LeagueNameIndex"
    key_schema {
      attribute_name = "server_id"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "league_name"
      key_type       = "RANGE"
    }
    projection_type    = "INCLUDE"
    non_key_attributes = ["league_id"]
  }

  global_secondary_index {
    name = "EventNameIndex"
    key_schema {
      attribute_name = "server_id"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "event_name"
      key_type       = "RANGE"
    }
    projection_type    = "INCLUDE"
    non_key_attributes = ["event_id", "start_time", "end_time", "description"]
  }
}
