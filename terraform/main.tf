data "aws_s3_bucket" "lambda_bucket" {
  bucket = var.bucket_name
}

data "aws_s3_object" "lambda_zip_latest" {
  bucket = var.bucket_name
  key    = "${var.app_name}/${var.app_name}-latest.zip"
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "LambdaExecutionRole-${var.app_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Effect = "Allow",
      Sid    = ""
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Layer with PyNaCl for cryptographic operations required by Discord auth
data "aws_lambda_layer_version" "pynacl_layer" {
  layer_name = "PyNaCl-311"
}

resource "aws_lambda_layer_version" "app_layer" {
  layer_name               = "${var.app_name}-layer"
  description              = "Lambda layer for dependencies of ${var.app_name}"
  s3_bucket                = var.bucket_name
  s3_key                   = var.app_lambda_layer_s3_key
  compatible_runtimes      = ["python${var.python_runtime}"]
  compatible_architectures = [var.architecture]
}

resource "aws_lambda_function" "bot_lambda" {
  function_name = "${var.app_name}-${var.deployment_env}"
  s3_bucket     = data.aws_s3_bucket.lambda_bucket.id
  s3_key        = data.aws_s3_object.lambda_zip_latest.key
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python${var.python_runtime}"
  architectures = [var.architecture]
  role          = aws_iam_role.lambda_exec_role.arn
  timeout       = 10
  layers = [
    data.aws_lambda_layer_version.pynacl_layer.arn,
    aws_lambda_layer_version.app_layer.arn
  ]
  environment {
    variables = {
      PUBLIC_KEY          = var.discord_public_key,
      STARTGG_API_TOKEN   = var.startgg_api_token
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.adomi_discord_server_table.name
    }
  }

  # Ensures Lambda updates only if the zip file changes
  source_code_hash = data.aws_s3_object.lambda_zip_latest.etag
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${var.app_name}-${var.deployment_env}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bot_lambda.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /${var.app_name}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "env_stage" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = var.deployment_env
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot_lambda.function_name
  principal     = "apigateway.amazonaws.com"

  # fully-qualified source ARN
  source_arn = "${aws_apigatewayv2_api.api.execution_arn}/${var.deployment_env}/POST/${var.app_name}"
}
