output "lambda_function_name" {
  value = aws_lambda_function.bot_lambda.function_name
}

output "api_url" {
  value = aws_apigatewayv2_api.api.api_endpoint
}
