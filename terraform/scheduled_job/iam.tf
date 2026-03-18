resource "aws_iam_role" "scheduled_job_role" {
  name = "LambdaExecutionRole-${var.scheduled_job_name}-${var.deployment_env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scheduled_job_basic_execution" {
  role       = aws_iam_role.scheduled_job_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "scheduled_job_policy" {
  name = "LambdaPolicy-${var.scheduled_job_name}-${var.deployment_env}"
  role = aws_iam_role.scheduled_job_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          data.aws_dynamodb_table.adomi_table.arn,
          "${data.aws_dynamodb_table.adomi_table.arn}/index/*"
        ]
      },
      {
        Sid    = "SQSSendMessage"
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:SendMessageBatch"]
        Resource = data.aws_sqs_queue.remove_role.arn
      },
      {
        Sid    = "GetStartggOAuthCredentials"
        Effect = "Allow"
        Action = "secretsmanager:GetSecretValue"
        Resource = data.aws_secretsmanager_secret.startgg_oauth_credentials.arn
      }
    ]
  })
}
