data "aws_dynamodb_table" "adomi_table" {
  # Table is owned by the infra root; name is single-sourced from config.env
  # (DYNAMODB_TABLE_BASE_NAME) via the deploy workflow.
  name = var.dynamodb_table_name
}

data "aws_sqs_queue" "remove_role" {
  name = "${var.sqs_worker_name}-${var.deployment_env}"
}

# Bot token secret is owned by the infra root; looked up by name (single-sourced
# from the deploy workflow) so this root can grant itself read access.
data "aws_secretsmanager_secret" "discord_bot_token" {
  name = var.discord_bot_token_secret_name
}

# start.gg API token secret is owned by the infra root; looked up by name so this root can grant
# itself read access for the reschedule scout (compares start.gg start times to stored ones).
data "aws_secretsmanager_secret" "startgg_api_token" {
  name = var.startgg_secret_name
}

data "aws_s3_object" "scheduled_job_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.scheduled_job_name}/${var.scheduled_job_name}-latest.zip"
}

data "aws_s3_object" "scheduled_job_layer_zip" {
  bucket = var.bucket_name
  key    = var.scheduled_job_layer_s3_key
}

data "aws_s3_object" "scheduled_job_layer_hash" {
  bucket = var.bucket_name
  key    = var.scheduled_job_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "scheduled_job_layer" {
  layer_name               = "${var.scheduled_job_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.scheduled_job_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.scheduled_job_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.scheduled_job_layer_hash.body)
}

module "scheduled_job" {
  source = "github.com/enpicie/tf-module-eventbridge-scheduled-lambda?ref=v1.3.0"

  name                = "${var.scheduled_job_name}-${var.deployment_env}"
  # 15-minute poller cadence: frequent enough for timely event cleanup and 24h reminders,
  # infrequent enough to keep Lambda/Discord API usage negligible.
  schedule_expression = "rate(15 minutes)"
  handler             = "handler.handler"
  runtime             = "python${var.python_runtime}"
  timeout             = 60
  iam_role_arn        = aws_iam_role.scheduled_job_role.arn

  s3_bucket        = var.bucket_name
  s3_key           = data.aws_s3_object.scheduled_job_zip_latest.key
  source_code_hash = data.aws_s3_object.scheduled_job_zip_latest.etag

  architecture = var.architecture
  layers       = [aws_lambda_layer_version.scheduled_job_layer.arn]

  environment_variables = {
    REGION                        = var.aws_region
    DISCORD_BOT_TOKEN_SECRET_NAME = data.aws_secretsmanager_secret.discord_bot_token.name
    DYNAMODB_TABLE_NAME           = data.aws_dynamodb_table.adomi_table.name
    REMOVE_ROLE_QUEUE_URL         = data.aws_sqs_queue.remove_role.url
    STARTGG_SECRET_NAME           = data.aws_secretsmanager_secret.startgg_api_token.name
  }
}
