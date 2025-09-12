# config.env settings passed in as ENV variables from GitHub Actions workflow
variable "app_name" {
  description = "The name of the application"
  type        = string
}

variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
}

variable "deployment_env" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket to store Lambda artifacts"
  type        = string
}

variable "discord_public_key" {
  description = "Public Key for Discord bot verification"
  type        = string
}
