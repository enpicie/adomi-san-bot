data "aws_dynamodb_table" "adomi_table" {
  name = "adomi-discord-server-data-${var.deployment_env}"
}

data "aws_sqs_queue" "remove_role" {
  name = var.sqs_worker_name
}

data "aws_s3_object" "event_poller_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.event_poller_name}/${var.event_poller_name}-latest.zip"
}

data "aws_s3_object" "event_poller_layer_zip" {
  bucket = var.bucket_name
  key    = var.event_poller_layer_s3_key
}

data "aws_s3_object" "event_poller_layer_hash" {
  bucket = var.bucket_name
  key    = var.event_poller_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "event_poller_layer" {
  layer_name               = "${var.event_poller_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.event_poller_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.event_poller_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.event_poller_layer_hash.body)
}

module "event_poller" {
  source = "github.com/enpicie/tf-module-eventbridge-scheduled-lambda?ref=v1.1.0"

  name                = "${var.event_poller_name}-${var.deployment_env}"
  schedule_expression = "rate(15 minutes)"
  handler             = "handler.handler"
  runtime             = "python${var.python_runtime}"
  timeout             = 60
  iam_role_arn        = aws_iam_role.event_poller_role.arn

  s3_bucket        = var.bucket_name
  s3_key           = data.aws_s3_object.event_poller_zip_latest.key
  source_code_hash = data.aws_s3_object.event_poller_zip_latest.etag

  layers = [aws_lambda_layer_version.event_poller_layer.arn]

  environment_variables = {
    REGION                = var.aws_region
    DISCORD_BOT_TOKEN     = var.discord_bot_token
    DYNAMODB_TABLE_NAME   = data.aws_dynamodb_table.adomi_table.name
    REMOVE_ROLE_QUEUE_URL = data.aws_sqs_queue.remove_role.url
  }
}
