# config.env settings passed in as ENV variables from GitHub Actions workflow
variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "sqs_worker_name" {
  description = "The name of the sqs worker lambda"
  type        = string
}

variable "sheets_agent_name" {
  description = "The name of the sheets agent Lambda and SQS queue"
  type        = string
}

variable "sheets_agent_lambda_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for the sheets agent"
  type        = string
}

variable "sheets_agent_lambda_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for the sheets agent"
  type        = string
}

variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
}

variable "python_runtime" {
  description = "Python runtime for Lambda (e.g., 3.11)"
  type        = string
}

variable "architecture" {
  description = "Architecture for Lambda (e.g., x86_64, arm64)"
  type        = string
  default     = "x86_64"
}

variable "deployment_env" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket to store Lambda artifacts"
  type        = string
}

variable "app_lambda_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for this application"
  type        = string
}

variable "app_lambda_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for this application"
  type        = string
}

variable "worker_lambda_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for the SQS worker"
  type        = string
}

variable "worker_lambda_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for the SQS worker"
  type        = string
}

variable "discord_public_key" {
  description = "Public Key for Discord bot verification"
  type        = string
}

variable "discord_bot_token" {
  description = "Discord bot token for authenticating with Discord API"
  type        = string
}

variable "startgg_api_key" {
  description = "Start.gg API key for accessing the start.gg GraphQL API"
  type        = string
  sensitive   = true
}

variable "startgg_oauth_client_id" {
  description = "start.gg OAuth application client ID"
  type        = string
}

variable "startgg_oauth_client_secret" {
  description = "start.gg OAuth application client secret"
  type        = string
  sensitive   = true
}

variable "google_service_account_email" {
  description = "Google service account email for Sheets API access"
  type        = string
}

variable "startgg_oauth_name" {
  description = "Name of the start.gg OAuth callback Lambda function"
  type        = string
}

variable "oauth_callback_lambda_layer_s3_key" {
  description = "S3 key for the start.gg OAuth callback Lambda layer zip"
  type        = string
}

variable "oauth_callback_lambda_layer_hash_s3_key" {
  description = "S3 key for the hash file of the start.gg OAuth callback Lambda layer zip"
  type        = string
}
