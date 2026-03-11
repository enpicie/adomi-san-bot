terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # backend "remote" {
  #   hostname     = "app.terraform.io"
  #   organization = "enpicie"
  #   workspaces {
  #     name = "adomi-san-bot-prod"
  #   }
  # }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}
