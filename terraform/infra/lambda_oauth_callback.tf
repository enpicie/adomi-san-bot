# ============================================================
# start.gg OAuth Callback Lambda
#
# Handles the OAuth redirect from start.gg after a user
# authorizes the bot. Exchanges the authorization code for
# access/refresh tokens and stores them in DynamoDB keyed
# to the user's Discord user ID.
#
# Route: GET /startgg/callback (on the shared API Gateway)
# ============================================================

# --- Secret ---

resource "aws_secretsmanager_secret" "startgg_oauth_credentials" {
  name        = "${var.app_name}-startgg-oauth-${var.deployment_env}"
  description = "start.gg OAuth client_id and client_secret for ${var.app_name}"
}

resource "aws_secretsmanager_secret_version" "startgg_oauth_credentials" {
  secret_id = aws_secretsmanager_secret.startgg_oauth_credentials.id
  secret_string = jsonencode({
    client_id     = var.startgg_oauth_client_id
    client_secret = var.startgg_oauth_client_secret
  })
}

# --- IAM Role ---

resource "aws_iam_role" "oauth_callback_exec_role" {
  name = "LambdaExecutionRole-${var.app_name}-oauth-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
      Effect    = "Allow"
      Sid       = ""
    }]
  })
}

resource "aws_iam_role_policy_attachment" "oauth_callback_basic_execution" {
  role       = aws_iam_role.oauth_callback_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "oauth_callback_dynamodb_policy" {
  name = "OAuthCallbackDynamoDBPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.oauth_callback_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "OAuthStateAndTokenAccess"
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:DeleteItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
      ]
      Resource = aws_dynamodb_table.adomi_discord_server_table.arn
    }]
  })
}

resource "aws_iam_role_policy" "oauth_callback_secrets_policy" {
  name = "OAuthCallbackSecretsPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.oauth_callback_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "GetOAuthCredentials"
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_secretsmanager_secret.startgg_oauth_credentials.arn
    }]
  })
}

# --- Lambda ---

data "aws_s3_object" "oauth_callback_lambda_zip" {
  bucket = var.bucket_name
  key    = "${var.startgg_oauth_name}/${var.startgg_oauth_name}-latest.zip"
}

data "aws_s3_object" "oauth_callback_layer_zip" {
  bucket = var.bucket_name
  key    = var.oauth_callback_lambda_layer_s3_key
}

data "aws_s3_object" "oauth_callback_layer_hash" {
  bucket = var.bucket_name
  key    = var.oauth_callback_lambda_layer_hash_s3_key
}

resource "aws_lambda_layer_version" "oauth_callback_layer" {
  layer_name               = "${var.startgg_oauth_name}-layer-${var.deployment_env}"
  description              = "Lambda layer for dependencies of ${var.startgg_oauth_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = data.aws_s3_object.oauth_callback_layer_zip.key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
  source_code_hash         = trimspace(data.aws_s3_object.oauth_callback_layer_hash.body)
}

resource "aws_lambda_function" "oauth_callback_lambda" {
  function_name    = "${var.app_name}-oauth-callback-${var.deployment_env}"
  s3_bucket        = var.bucket_name
  s3_key           = data.aws_s3_object.oauth_callback_lambda_zip.key
  handler          = "handler.handler"
  runtime          = "python${var.python_runtime}"
  architectures    = [var.architecture]
  role             = aws_iam_role.oauth_callback_exec_role.arn
  timeout          = 10
  layers           = [aws_lambda_layer_version.oauth_callback_layer.arn]
  source_code_hash = data.aws_s3_object.oauth_callback_lambda_zip.etag

  environment {
    variables = {
      REGION                    = var.aws_region
      DYNAMODB_TABLE_NAME       = aws_dynamodb_table.adomi_discord_server_table.name
      STARTGG_OAUTH_SECRET_NAME = aws_secretsmanager_secret.startgg_oauth_credentials.name
      OAUTH_REDIRECT_URI        = "${aws_apigatewayv2_stage.env_stage.invoke_url}/startgg/callback"
      DISCORD_BOT_TOKEN         = var.discord_bot_token
    }
  }
}

# --- API Gateway Integration & Route ---

resource "aws_apigatewayv2_integration" "oauth_callback_integration" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.oauth_callback_lambda.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "oauth_callback" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /startgg/callback"
  target    = "integrations/${aws_apigatewayv2_integration.oauth_callback_integration.id}"
}

resource "aws_lambda_permission" "apigw_oauth_callback" {
  statement_id  = "AllowAPIGatewayInvokeOAuthCallback"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.oauth_callback_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/${var.deployment_env}/GET/startgg/callback"
}
