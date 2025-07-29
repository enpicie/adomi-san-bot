# No token needed. Authenticating to HCP Terraform via repo secret withh TF_API_TOKEN.
terraform {
  required_providers {
    tfe = {
      version = "~> 0.67.1"
    }
  }
}
