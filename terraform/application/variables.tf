variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-2" # Ohio
}

variable "app_name" {
  description = "Path to the ZIP file for Lambda deployment"
  type        = string
  default     = "startgg-bracket-helper-bot"
}

# Set via Workspace Vars provisioned via workspace_config
variable "env" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket to store Lambda artifacts"
  type        = string
}
