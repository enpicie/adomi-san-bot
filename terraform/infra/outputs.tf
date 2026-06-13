output "lambda_function_name" {
  description = "Name of the main bot Lambda function"
  value       = aws_lambda_function.bot_lambda.function_name
}

output "api_url" {
  description = "Base endpoint of the API Gateway HTTP API receiving Discord interactions"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table storing server, event, and league data"
  value       = aws_dynamodb_table.adomi_discord_server_table.name
}

output "remove_role_queue_url" {
  description = "URL of the SQS queue for async participant role removal"
  value       = aws_sqs_queue.remove_role.url
}

output "remove_role_queue_arn" {
  description = "ARN of the SQS queue for async participant role removal"
  value       = aws_sqs_queue.remove_role.arn
}

output "oauth_callback_url" {
  description = "Register this as the redirect URI in your start.gg OAuth application settings"
  value       = "${aws_apigatewayv2_stage.env_stage.invoke_url}/startgg/callback"
}
