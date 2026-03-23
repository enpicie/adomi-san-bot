resource "aws_sqs_queue" "sheets_agent" {
  name                       = var.sheets_agent_name
  visibility_timeout_seconds = 540
  message_retention_seconds  = 86400
}

data "aws_s3_object" "sheets_agent_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.sheets_agent_name}/${var.sheets_agent_name}-latest.zip"
}

data "aws_s3_object" "sheets_agent_layer_zip" {
  bucket = var.bucket_name
  key    = var.sheets_agent_lambda_layer_s3_key
}

data "aws_s3_object" "sheets_agent_layer_hash" {
  bucket = var.bucket_name
  key    = var.sheets_agent_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "sheets_agent_layer" {
  layer_name               = "${var.sheets_agent_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.sheets_agent_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.sheets_agent_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.sheets_agent_layer_hash.body)
}

resource "aws_lambda_function" "sheets_agent" {
  function_name = "${var.sheets_agent_name}-${var.deployment_env}"
  s3_bucket     = data.aws_s3_bucket.lambda_bucket.id
  s3_key        = data.aws_s3_object.sheets_agent_zip_latest.key
  handler       = "handler.handler"
  runtime       = "python${var.python_runtime}"
  role          = aws_iam_role.sheets_agent_role.arn
  timeout       = 480
  memory_size   = 512

  layers = [
    aws_lambda_layer_version.sheets_agent_layer.arn
  ]

  environment {
    variables = {
      REGION                       = var.aws_region
      DISCORD_BOT_TOKEN            = var.discord_bot_token
      DYNAMODB_TABLE_NAME          = aws_dynamodb_table.adomi_discord_server_table.name
      REMOVE_ROLE_QUEUE_URL        = aws_sqs_queue.remove_role.url
      GOOGLE_SHEETS_SECRET_NAME    = data.aws_secretsmanager_secret.sheets_credentials.name
      GOOGLE_SERVICE_ACCOUNT_EMAIL = var.google_service_account_email
    }
  }

  source_code_hash = data.aws_s3_object.sheets_agent_zip_latest.etag
}

resource "aws_lambda_event_source_mapping" "sheets_agent_trigger" {
  event_source_arn = aws_sqs_queue.sheets_agent.arn
  function_name    = aws_lambda_function.sheets_agent.arn
  batch_size       = 1
}

# ── IAM ──────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "sheets_agent_role" {
  name = "LambdaExecutionRole-${var.sheets_agent_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sheets_agent_basic_execution" {
  role       = aws_iam_role.sheets_agent_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "sheets_agent_policy" {
  name = "LambdaPolicy-${var.sheets_agent_name}-${var.deployment_env}"
  role = aws_iam_role.sheets_agent_role.id

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
        Resource = aws_sqs_queue.sheets_agent.arn
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
          "dynamodb:UpdateItem",
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
      }
    ]
  })
}
