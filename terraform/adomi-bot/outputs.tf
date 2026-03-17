output "lambda_function_name" {
  value = aws_lambda_function.bot_lambda.function_name
}

output "api_url" {
  value = aws_apigatewayv2_api.api.api_endpoint
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.adomi_discord_server_table.name
}

output "remove_role_queue_url" {
  value = aws_sqs_queue.remove_role.url
}

output "remove_role_queue_arn" {
  value = aws_sqs_queue.remove_role.arn
}
