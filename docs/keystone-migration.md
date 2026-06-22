# Keystone migration plan — adomi-san-bot

Migrate adomi off the current secrets pattern onto the platform [env/secrets keystone](https://github.com/enpicie/platform/blob/main/docs/env-and-secrets.md).

> **Status: PLAN ONLY.** This PR adds the `config/app-config.yaml` manifest and this plan. The Terraform and runtime changes below are **not yet applied** — they require a `terraform plan` review and a runtime test that only the owner can run against AWS. Do not merge until the checklist passes.

## Why
Today `terraform/infra/secrets.tf` mixes two patterns:
- `startgg_api_token` and `discord_bot_token` are **created with their values via Terraform** (`aws_secretsmanager_secret_version` ← `var.*`), so the secret value lands in **Terraform state** (a leak surface).
- `sheets_credentials` is imported as a pre-populated data source (correct — value never in state).

The keystone replaces all three with one JSON secret `adomi-san-bot/{env}`, with Terraform owning the container + IAM only.

## Target state

### 1. Terraform — replace `secrets.tf` with the module
```hcl
module "app_config" {
  source = "git::https://github.com/enpicie/tf-module-app-config.git?ref=v0.1.0"

  app_name            = var.app_name
  deployment_env      = var.deployment_env
  execution_role_name = aws_iam_role.lambda_exec_role.name
}
```
This creates `adomi-san-bot/{env}` + a scoped `GetSecretValue` policy on the Lambda exec role, replacing the three `aws_secretsmanager_secret*` resources and the hand-written `lambda_secrets_policy`.

Remove the now-unused vars: `startgg_api_key`, `discord_bot_token`, `discord_bot_token_secret_name`, `google_sheets_secret_name`.

### 2. State migration (the careful part)
The three old secrets must **not** be deleted (they hold live values). Options:
- Keep the existing secrets and have the module adopt the same name, OR
- Create the new `adomi-san-bot/{env}` secret, **populate it** (step 3), cut runtime over (step 4), then delete the old secrets in a follow-up.

Recommended: additive — stand up the new secret alongside, migrate runtime, then remove the old resources in a second PR. Review `terraform plan` to confirm **no destroy** of a populated secret happens unexpectedly.

### 3. Populate the new secret (out-of-band — never in Terraform)
```bash
aws secretsmanager put-secret-value \
  --secret-id "adomi-san-bot/prod" \
  --secret-string '{"STARTGG_API_TOKEN":"...","DISCORD_BOT_TOKEN":"...","GOOGLE_SHEETS_CREDS":"<json>"}'
```

### 4. Runtime code — fetch one secret, parse keys
Currently `src/constants.py` reads three secret *names* from env and `src/commands/event/startgg/startgg_api.py` (and the discord/sheets paths) fetch each separately. Change to: fetch `adomi-san-bot/{env}` once, `json.loads` it, read keys `STARTGG_API_TOKEN` / `DISCORD_BOT_TOKEN` / `GOOGLE_SHEETS_CREDS`. Use the AWS Parameters and Secrets Lambda Extension for caching where possible.

Files touched: `src/constants.py`, `src/commands/event/startgg/startgg_api.py`, plus wherever the Discord token and Sheets creds are read.

### 5. Pipeline — add fail-fast validation
In the deploy workflow, after AWS creds are configured and before deploy:
```yaml
- uses: enpicie/gh-action-validate-config@v0.1.0
  with:
    app_name: adomi-san-bot
    deployment_env: prod
    aws_region: ${{ env.AWS_REGION }}
```

## Validation checklist (owner)
- [ ] `terraform plan` shows the new secret + IAM, and **no destroy** of a populated secret
- [ ] New `adomi-san-bot/prod` secret populated with all required keys
- [ ] Runtime code reads the single JSON secret; bot + scheduled job tested
- [ ] `gh-action-validate-config` passes in the pipeline
- [ ] Old `*-startgg-api-token-*` / discord / sheets secrets removed (follow-up PR)
- [ ] Confirm no secret value appears in `terraform state pull` output

## Rollback
Until the old secrets are deleted (step 5 / follow-up), reverting the runtime code restores the previous behavior with no data loss.
