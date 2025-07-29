data "tfe_organization" "hcp_organization" {
  name = "enpicie"
}


data "tfe_workspace" "prod_workspace" {
  name         = "startgg-bracket-helper-bot-prod"
  organization = data.tfe_organization.hcp_organization.name
}

resource "tfe_variable_set" "prod_varset" {
  name         = "startgg-bracket-helper-bot Prod Varset"
  description  = "Prod config vars for startgg-bracket-helper-bot"
  organization = data.tfe_organization.hcp_organization.name
}

resource "tfe_workspace_variable_set" "prod_workspace_varset" {
  variable_set_id = tfe_variable_set.prod_varset.id
  workspace_id    = data.tfe_workspace.prod_workspace.id
}

resource "tfe_variable" "prod_env" {
  key             = "env"
  value           = "prod"
  category        = "terraform"
  variable_set_id = tfe_variable_set.prod_varset.id
}

resource "tfe_variable" "bucket_name" {
  key             = "bucket_name"
  value           = "enpicie-prod-lambda-artifacts"
  category        = "terraform"
  variable_set_id = tfe_variable_set.prod_varset.id
}
