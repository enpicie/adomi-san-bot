resource "aws_sqs_queue" "deferred_worker" {
  name = "${var.deferred_worker_name}-${var.deployment_env}"

  # Must exceed the deferred_worker Lambda timeout (480s below) so a message is not
  # redelivered while a consumer invocation is still running.
  visibility_timeout_seconds = 540
  message_retention_seconds  = 86400
}

data "aws_s3_object" "deferred_worker_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.deferred_worker_name}/${var.deferred_worker_name}-latest.zip"
}

data "aws_s3_object" "deferred_worker_layer_zip" {
  bucket = var.bucket_name
  key    = var.deferred_worker_lambda_layer_s3_key
}

data "aws_s3_object" "deferred_worker_layer_hash" {
  bucket = var.bucket_name
  key    = var.deferred_worker_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "deferred_worker_layer" {
  layer_name               = "${var.deferred_worker_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.deferred_worker_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.deferred_worker_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.deferred_worker_layer_hash.body)
}

resource "aws_lambda_function" "deferred_worker" {
  function_name = "${var.deferred_worker_name}-${var.deployment_env}"
  s3_bucket     = data.aws_s3_bucket.lambda_bucket.id
  s3_key        = data.aws_s3_object.deferred_worker_zip_latest.key
  handler       = "handler.handler"
  runtime       = "python${var.python_runtime}"
  architectures = [var.architecture]
  role          = aws_iam_role.deferred_worker_role.arn
  timeout       = 480
  memory_size   = 512

  layers = [
    aws_lambda_layer_version.deferred_worker_layer.arn
  ]

  environment {
    variables = {
      REGION                       = var.aws_region
      DISCORD_BOT_TOKEN_SECRET_NAME = aws_secretsmanager_secret.discord_bot_token.name
      DYNAMODB_TABLE_NAME          = aws_dynamodb_table.adomi_discord_server_table.name
      REMOVE_ROLE_QUEUE_URL        = aws_sqs_queue.remove_role.url
      GOOGLE_SHEETS_SECRET_NAME    = data.aws_secretsmanager_secret.sheets_credentials.name
      GOOGLE_SERVICE_ACCOUNT_EMAIL = var.google_service_account_email
      STARTGG_SECRET_NAME          = aws_secretsmanager_secret.startgg_api_token.name
    }
  }

  source_code_hash = data.aws_s3_object.deferred_worker_zip_latest.etag
}

resource "aws_lambda_event_source_mapping" "deferred_worker_trigger" {
  event_source_arn = aws_sqs_queue.deferred_worker.arn
  function_name    = aws_lambda_function.deferred_worker.arn
  batch_size       = 1
}

# ── IAM ──────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "deferred_worker_role" {
  name = "LambdaExecutionRole-${var.deferred_worker_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "deferred_worker_basic_execution" {
  role       = aws_iam_role.deferred_worker_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "deferred_worker_policy" {
  name = "LambdaPolicy-${var.deferred_worker_name}-${var.deployment_env}"
  role = aws_iam_role.deferred_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.deferred_worker.arn
      },
      {
        Sid    = "SQSSendRoleRemoval"
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:SendMessageBatch"]
        Resource = aws_sqs_queue.remove_role.arn
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.adomi_discord_server_table.arn,
          "${aws_dynamodb_table.adomi_discord_server_table.arn}/index/*"
        ]
      },
      {
        Sid      = "GetSheetsCredentials"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = data.aws_secretsmanager_secret.sheets_credentials.arn
      },
      {
        Sid      = "GetDiscordBotToken"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_secretsmanager_secret.discord_bot_token.arn
      },
      {
        Sid      = "GetStartggApiToken"
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = aws_secretsmanager_secret.startgg_api_token.arn
      }
    ]
  })
}
