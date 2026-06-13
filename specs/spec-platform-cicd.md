# Platform CI/CD Spec

*Defines how all projects in this org deploy infrastructure and artifacts.*
*Stack-agnostic. Applies to every project regardless of language or cloud provider.*
*Pair with General Spec, a stack spec, and an app spec.*

---

## 1. Purpose

This spec defines the standard CI/CD patterns for this platform. Every project deploys using the same composite actions, the same Terraform conventions, and the same workflow structure. The goal is zero per-project CI/CD invention — projects configure, not build.

---

## 2. Composite Actions

All composite actions live in the `enpicie` org. Projects reference them by version tag — never `@main`. Pin to a specific version tag for reproducibility.

### Terraform Run

**`enpicie/gh-action-workflow-terraform-run`**
Runs OpenTofu plan and apply via OIDC. All infrastructure changes go through this action.
https://github.com/enpicie/gh-action-workflow-terraform-run

### Lambda Layer Build + Upload

**`enpicie/gh-action-workflow-build-python-lambda-layer-zip`**
Installs Python dependencies, zips them, uploads to S3 as a Lambda layer artifact.
https://github.com/enpicie/action-workflow-build-python-lambda-layer-zip

### Lambda Zip Upload

**`enpicie/gh-action-workflow-upload-lambda-zip`**
Zips Lambda source code and uploads to S3 for deployment.

### S3 Upload

**`enpicie/gh-action-workflow-s3-upload`**
Uploads a build artifact to S3. Used for frontend dist after Terraform provisions the bucket.

---

## 3. Workflow Structure — Required Pattern

Every project uses this three-file workflow structure:

```
.github/
  deployment.env          # project config — all env-specific values live here
  workflows/
    release.yml           # root trigger — tags + workflow_dispatch
    workflow-build.yml    # reusable build — workflow_call
    workflow-deploy.yml   # reusable deploy — workflow_call (the deploy-infra pattern)
```

### `.github/deployment.env`

All project-specific configuration lives here. Never hardcode values in workflow files — source them from this file via the `config` job.

```bash
APP_NAME=dia
AWS_REGION=us-east-2
DEPLOYMENT_ENV=prod
```

### `release.yml` — Root Trigger

Triggers on version tags and `workflow_dispatch`. Three jobs: `config` -> `build` -> `deploy`.

```yaml
name: Release Pipeline
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  config:
    runs-on: ubuntu-latest
    outputs:
      app_name: ${{ steps.vars.outputs.app_name }}
      aws_region: ${{ steps.vars.outputs.aws_region }}
      deployment_env: ${{ steps.vars.outputs.deployment_env }}
    steps:
      - uses: actions/checkout@v4
      - name: Load deployment config
        id: vars
        run: |
          source .github/deployment.env
          echo "app_name=$APP_NAME" >> $GITHUB_OUTPUT
          echo "aws_region=$AWS_REGION" >> $GITHUB_OUTPUT
          echo "deployment_env=$DEPLOYMENT_ENV" >> $GITHUB_OUTPUT

  build:
    needs: config
    uses: ./.github/workflows/workflow-build.yml
    with:
      aws_region: ${{ needs.config.outputs.aws_region }}
      app_name: ${{ needs.config.outputs.app_name }}
      image_tag: ${{ github.ref_name }}
    secrets:
      AWS_ROLE_ARN_S3: ${{ secrets.AWS_ROLE_ARN_S3 }}

  deploy:
    needs: [config, build]
    uses: ./.github/workflows/workflow-deploy.yml
    with:
      aws_region: ${{ needs.config.outputs.aws_region }}
      app_name: ${{ needs.config.outputs.app_name }}
      deployment_env: ${{ needs.config.outputs.deployment_env }}
      app_version: ${{ github.sha }}
    secrets:
      AWS_ROLE_ARN_S3_CLOUDFRONT: ${{ secrets.AWS_ROLE_ARN_S3_CLOUDFRONT }}
      AWS_ROLE_ARN_LAMBDA_APIGW: ${{ secrets.AWS_ROLE_ARN_LAMBDA_APIGW }}
      AWS_ROLE_ARN_S3: ${{ secrets.AWS_ROLE_ARN_S3 }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
```

### `workflow-build.yml` — Reusable Build

Handles artifact building. Outputs artifact references consumed by `workflow-deploy.yml`. Stack spec defines what gets built (Lambda zips, Docker images, frontend dist, etc.).

### `workflow-deploy.yml` — Reusable Deploy

The deployment steps. All Terraform runs live here. Declared with `on: workflow_call`. Stack spec defines the Terraform steps.

### Rules

- **`deployment.env` is the single source of project config.** The `config` job sources it and passes values downstream. No other workflow file contains hardcoded project values.
- **`app_version` is always `github.sha`** — not the tag. Ensures artifact traceability back to a specific commit regardless of tag name.
- **ECR repository names follow `{app_name}/{component}`** convention — e.g. `dia/backend`. Derived from `app_name`, never hardcoded separately.
- **`workflow_dispatch` is always present** on the root trigger for manual deploys without pushing a tag.

---

## 4. Terraform Conventions

### Backend — S3 State

Every project uses remote state in S3. The Terraform backend block is always empty — configuration is injected by the composite action:

```hcl
terraform {
  backend "s3" {}
}
```

Never hardcode backend configuration. The composite action handles bucket, region, and lock table.

### State Key Convention

State keys follow this pattern exactly:

```
projects/{app_name}/{env}/{component}.tfstate
```

Examples:

```
projects/dia/prod/frontend.tfstate
projects/dia/prod/backend.tfstate
projects/find-my-fgc/prod/frontend.tfstate
projects/find-my-fgc/prod/backend.tfstate
```

One state file per logical infrastructure component, not one per project. Splitting state by component means each Terraform run uses the minimum IAM permissions needed.

### IAM Roles — Scoped Per Resource Group

Never use a single IAM role for an entire project's infrastructure. Roles are scoped to the resource types they manage:

```
AWS_ROLE_ARN_S3_CLOUDFRONT        # frontend: S3 + CloudFront only
AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS # backend: Lambda + API GW + DDB + SQS
AWS_ROLE_ARN_EVENTBRIDGE_LAMBDA   # scheduled jobs: EventBridge + Lambda
AWS_ROLE_ARN_ECS_ALB              # containers: ECS + ALB
AWS_ROLE_ARN_S3                   # artifact uploads: S3 only
```

Each Terraform run step uses the role scoped to only what that component needs.
Available roles: https://github.com/enpicie/aws-tf-iam-roles

### Multiple Terraform Runs Per Deploy

A single deploy workflow commonly runs Terraform multiple times — once per infrastructure component, each with its own role and state key:

```yaml
- name: Deploy Frontend via Terraform
  uses: enpicie/gh-action-workflow-terraform-run@v1.0.0
  with:
    aws_role_arn: ${{ secrets.AWS_ROLE_ARN_S3_CLOUDFRONT }}
    state_key: projects/${{ inputs.app_name }}/${{ inputs.deployment_env }}/frontend.tfstate
    tf_directory: ./terraform/frontend
    tf_vars: |
      TF_VAR_app_name=${{ inputs.app_name }}-frontend
      TF_VAR_deployment_env=${{ inputs.deployment_env }}
      TF_VAR_aws_region=${{ inputs.aws_region }}

- name: Deploy Backend via Terraform
  uses: enpicie/gh-action-workflow-terraform-run@v1.0.0
  with:
    aws_role_arn: ${{ secrets.AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS }}
    state_key: projects/${{ inputs.app_name }}/${{ inputs.deployment_env }}/backend.tfstate
    tf_directory: ./terraform/backend
    tf_vars: |
      TF_VAR_app_name=${{ inputs.app_name }}-backend
      TF_VAR_deployment_env=${{ inputs.deployment_env }}
      TF_VAR_aws_region=${{ inputs.aws_region }}
```

### Passing Variables

`tf_vars` takes `TF_VAR_*` assignments, one per line. OpenTofu maps `TF_VAR_foo` to `var.foo` automatically.

Non-sensitive values come from `inputs.*`. Sensitive values come from `secrets.*`. Never swap these — inputs are logged, secrets are masked.

```yaml
tf_vars: |
  TF_VAR_app_name=${{ inputs.app_name }}
  TF_VAR_deployment_env=${{ inputs.deployment_env }}
  TF_VAR_aws_region=${{ inputs.aws_region }}
  TF_VAR_api_key=${{ secrets.API_KEY }}
```

### Chaining Terraform Outputs

When a later step needs a value provisioned by Terraform (e.g. S3 bucket name, CloudFront distribution ID), query it from the state after the Terraform run completes:

```yaml
- name: Get S3 bucket name
  id: get-bucket
  run: |
    BUCKET=$(tofu -chdir=./terraform/frontend output -raw bucket_name)
    echo "bucket_name=$BUCKET" >> $GITHUB_OUTPUT

- name: Upload to S3
  uses: enpicie/gh-action-workflow-s3-upload@v1.0.0
  with:
    bucket_name: ${{ steps.get-bucket.outputs.bucket_name }}
    aws_role_arn: ${{ secrets.AWS_ROLE_ARN_S3 }}
```

Never hardcode resource identifiers that Terraform manages. Always read from outputs.

---

## 5. Terraform Directory Structure

```
terraform/
  frontend/
    main.tf
    variables.tf
    outputs.tf        # bucket_name, distribution_id, etc.
  backend/
    main.tf
    variables.tf
    outputs.tf
  [component]/
    main.tf
    variables.tf
    outputs.tf
```

One directory per infrastructure component. Each directory is an independent Terraform root — its own state, its own IAM role. Variables are declared in `variables.tf` with no defaults for required values, so missing vars fail fast at plan time.

---

## 6. Workflow Inputs and Secrets

**`deploy-infra.yml` inputs** — values that vary by environment or run. Declared under `on.workflow_call.inputs`. Always typed. Required inputs have `required: true`.

Common inputs across all projects:

```yaml
inputs:
  app_name:
    description: Name of the application
    required: true
    type: string
  deployment_env:
    description: Environment (e.g. prod)
    required: true
    type: string
  aws_region:
    description: AWS region
    required: true
    type: string
  app_version:
    description: Version tag for the artifact
    required: false
    type: string
```

**`deploy-infra.yml` secrets** — sensitive values passed from the caller. Declared under `on.workflow_call.secrets`. IAM role ARNs are always secrets, never inputs — they are sensitive and must not appear in logs.

```yaml
secrets:
  AWS_ROLE_ARN_S3_CLOUDFRONT:
    required: true
  AWS_ROLE_ARN_LAMBDA_APIGW_DDB_SQS:
    required: true
```

---

## 7. Plan vs Apply

By default the Terraform action runs both plan and apply. On pull requests, run plan only — never apply on a PR:

```yaml
apply: ${{ github.ref == 'refs/heads/main' && 'true' || 'false' }}
```

Always include this conditional. Never apply infrastructure changes from a PR branch.

---

## 8. Workflow Permissions

Every job that uses the Terraform composite action or any AWS action via OIDC requires:

```yaml
permissions:
  id-token: write   # required for OIDC
  contents: read
```

Set at the job level, not the workflow level, so permissions are scoped as tightly as possible.

---

## 9. Terraform Project Structure

On init, Claude Code generates:

```
terraform/
  frontend/           # if project has a frontend
    main.tf
    variables.tf
    outputs.tf
  backend/            # if project has a backend
    main.tf
    variables.tf
    outputs.tf
```

Every `variables.tf` declares all variables passed via `tf_vars`. Every `outputs.tf` exposes values needed by subsequent workflow steps. No Terraform resource identifier is hardcoded in a workflow file.

---

## 10. Logging Terraform Inputs

Before any Terraform run on complex deployments, log the resolved input values for debugging. Use environment variables to prevent secret interpolation in the log:

```yaml
- name: Log Terraform inputs
  shell: bash
  run: |
    echo "app_name=${APP_NAME}"
    echo "deployment_env=${DEPLOYMENT_ENV}"
    echo "aws_region=${AWS_REGION}"
  env:
    APP_NAME: ${{ inputs.app_name }}
    DEPLOYMENT_ENV: ${{ inputs.deployment_env }}
    AWS_REGION: ${{ inputs.aws_region }}
```

Never echo secrets directly. Only log non-sensitive inputs.

---

## 11. Prerequisites — Before First Deploy

These must exist before any project can use this platform:

- [ ] AWS account bootstrapped with the `tf-backend.yml` stack — provisions S3 state bucket, DynamoDB lock table, and OIDC provider
- [ ] IAM roles provisioned via https://github.com/enpicie/aws-tf-iam-roles — scoped to the resource types this project needs
- [ ] IAM role ARNs added to GitHub Actions secrets in this repo
- [ ] Composite action versions confirmed — check each action repo for latest release tag

---

## 12. Anti-Patterns — Never Do These

- **Never hardcode project config values in workflow files.** All values (`app_name`, `aws_region`, `deployment_env`) live in `.github/deployment.env` and are sourced by the `config` job.
- **Never use `@main` for composite action refs.** Always pin to a version tag.
- **Never hardcode AWS account IDs, bucket names, or distribution IDs** in workflow files — read from Terraform outputs.
- **Never put IAM role ARNs in `inputs`** — they are secrets and must be masked.
- **Never use a single IAM role for an entire project** — scope roles to resource groups.
- **Never apply Terraform on a PR branch** — plan only, apply on merge to main.
- **Never put sensitive values in `inputs`** — inputs are logged, secrets are masked.
- **Never hardcode the S3 backend configuration** — always use an empty backend block.

---

*Platform CI/CD Spec — v1.0*
*Implements org-standard deployment patterns using platform composite actions.*
*Pair with General Spec, a stack spec, and an app spec.*
