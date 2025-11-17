resource "aws_sqs_queue" "remove_role" {
  name                       = "remove-role-queue"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
}

data "aws_s3_object" "worker_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.sqs_worker_name}/${var.sqs_worker_name}-latest.zip"
}

data "aws_s3_object" "worker_layer_zip" {
  bucket = var.bucket_name
  key    = var.worker_lambda_layer_s3_key
}

data "aws_s3_object" "worker_layer_hash" {
  bucket = var.bucket_name
  key    = var.worker_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "worker_layer" {
  layer_name               = "${var.sqs_worker_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.app_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.worker_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.worker_layer_hash.body)
}

resource "aws_lambda_function" "remove_role_worker" {
  function_name = "${var.sqs_worker_name}-${var.deployment_env}"
  handler       = "handler.handler"
  runtime       = "python${var.python_runtime}"
  role          = aws_iam_role.worker_role.arn

  layers = [
    aws_lambda_layer_version.worker_layer.arn
  ]
  environment {
    variables = {
      DISCORD_BOT_TOKEN = var.discord_bot_token
    }
  }

  # Ensures Lambda updates only if the zip file changes
  source_code_hash = data.aws_s3_object.worker_zip_latest.etag
}

resource "aws_lambda_event_source_mapping" "remove_role_trigger" {
  event_source_arn = aws_sqs_queue.remove_role.arn
  function_name    = aws_lambda_function.remove_role_worker.arn
  batch_size       = 10
}
