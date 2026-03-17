# config.env settings passed in as ENV variables from GitHub Actions workflow
variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "event_poller_name" {
  description = "The name of the event poller Lambda function"
  type        = string
}

variable "sqs_worker_name" {
  description = "Name of the SQS worker (used to look up the remove_role queue)"
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
  default     = "arm64"
}

variable "deployment_env" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket storing Lambda artifacts"
  type        = string
}

variable "event_poller_layer_s3_key" {
  description = "S3 key for .zip of Lambda layer built for event_poller"
  type        = string
}

variable "event_poller_layer_hash_s3_key" {
  description = "S3 key for .hash file for Lambda layer built for event_poller"
  type        = string
}

variable "discord_bot_token" {
  description = "Discord bot token for authenticating with Discord API"
  type        = string
  sensitive   = true
}
