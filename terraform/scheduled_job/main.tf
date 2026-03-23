data "aws_dynamodb_table" "adomi_table" {
  name = "adomi-discord-server-data-${var.deployment_env}"
}

data "aws_sqs_queue" "remove_role" {
  name = "${var.sqs_worker_name}-${var.deployment_env}"
}

data "aws_secretsmanager_secret" "startgg_oauth_credentials" {
  name = "${var.app_name}-startgg-oauth-${var.deployment_env}"
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
  source = "github.com/enpicie/tf-module-eventbridge-scheduled-lambda?ref=v1.2.0"

  name                = "${var.scheduled_job_name}-${var.deployment_env}"
  schedule_expression = "rate(15 minutes)"
  handler             = "handler.handler"
  runtime             = "python${var.python_runtime}"
  timeout             = 60
  iam_role_arn        = aws_iam_role.scheduled_job_role.arn

  s3_bucket        = var.bucket_name
  s3_key           = data.aws_s3_object.scheduled_job_zip_latest.key
  source_code_hash = data.aws_s3_object.scheduled_job_zip_latest.etag

  layers = [aws_lambda_layer_version.scheduled_job_layer.arn]

  environment_variables = {
    REGION                    = var.aws_region
    DISCORD_BOT_TOKEN         = var.discord_bot_token
    DYNAMODB_TABLE_NAME       = data.aws_dynamodb_table.adomi_table.name
    REMOVE_ROLE_QUEUE_URL     = data.aws_sqs_queue.remove_role.url
    STARTGG_OAUTH_SECRET_NAME = data.aws_secretsmanager_secret.startgg_oauth_credentials.name
  }
}
