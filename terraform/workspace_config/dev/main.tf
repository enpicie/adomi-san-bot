data "tfe_organization" "hcp_organization" {
  name = "enpicie"
}

data "tfe_workspace" "dev_workspace" {
  name         = "startgg-bracket-helper-bot-dev"
  organization = data.tfe_organization.hcp_organization.name
}

resource "tfe_variable_set" "dev_varset" {
  name         = "startgg-bracket-helper-bot Dev Varset"
  description  = "Dev config vars for startgg-bracket-helper-bot"
  organization = data.tfe_organization.hcp_organization.name
}

resource "tfe_workspace_variable_set" "dev_workspace_varset" {
  variable_set_id = tfe_variable_set.dev_varset.id
  workspace_id    = data.tfe_workspace.dev_workspace.id
}

resource "tfe_variable" "dev_env" {
  key             = "env"
  value           = "dev"
  category        = "terraform"
  variable_set_id = tfe_variable_set.dev_varset.id
}

resource "tfe_variable" "bucket_name" {
  key             = "bucket_name"
  value           = "enpicie-dev-lambda-artifacts"
  category        = "terraform"
  variable_set_id = tfe_variable_set.dev_varset.id
}

