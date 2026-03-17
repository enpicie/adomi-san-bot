resource "aws_iam_role" "event_poller_role" {
  name = "LambdaExecutionRole-${var.event_poller_name}-${var.deployment_env}"

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

resource "aws_iam_role_policy_attachment" "event_poller_basic_execution" {
  role       = aws_iam_role.event_poller_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "event_poller_policy" {
  name = "LambdaPolicy-${var.event_poller_name}-${var.deployment_env}"
  role = aws_iam_role.event_poller_role.id

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
      }
    ]
  })
}
