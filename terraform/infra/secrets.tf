resource "aws_secretsmanager_secret" "startgg_api_token" {
  name        = "${var.app_name}-startgg-api-token-${var.deployment_env}"
  description = "Start.gg API token for ${var.app_name}"
}

resource "aws_secretsmanager_secret_version" "startgg_api_token" {
  secret_id     = aws_secretsmanager_secret.startgg_api_token.id
  secret_string = var.startgg_api_key
}

# Discord bot token — stored in Secrets Manager and fetched by the Lambdas at
# runtime, rather than injected as a plaintext Lambda environment variable.
# Name is single-sourced from the deploy workflow (matches the scheduled_job root).
resource "aws_secretsmanager_secret" "discord_bot_token" {
  name        = var.discord_bot_token_secret_name
  description = "Discord bot token for ${var.app_name}"
}

resource "aws_secretsmanager_secret_version" "discord_bot_token" {
  secret_id     = aws_secretsmanager_secret.discord_bot_token.id
  secret_string = var.discord_bot_token
}

# Secret already exists and is populated manually - import as data source.
# Name is single-sourced from config.env (GOOGLE_SHEETS_SECRET_NAME) via the deploy workflow.
data "aws_secretsmanager_secret" "sheets_credentials" {
  name = var.google_sheets_secret_name
}

resource "aws_iam_role_policy" "lambda_secrets_policy" {
  name = "LambdaSecretsPolicy-${var.app_name}-${var.deployment_env}"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "GetStartggApiToken",
        Effect   = "Allow",
        Action   = "secretsmanager:GetSecretValue",
        Resource = aws_secretsmanager_secret.startgg_api_token.arn
      },
      {
        Sid      = "GetSheetsCredentials",
        Effect   = "Allow",
        Action   = "secretsmanager:GetSecretValue",
        Resource = data.aws_secretsmanager_secret.sheets_credentials.arn
      },
      {
        Sid      = "GetDiscordBotToken",
        Effect   = "Allow",
        Action   = "secretsmanager:GetSecretValue",
        Resource = aws_secretsmanager_secret.discord_bot_token.arn
      }
    ]
  })
}
