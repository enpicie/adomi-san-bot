# adomi-san-bot

This is Adomi-san, a Discord bot to help streamline and automate workflows for managing netplay brackets run via start.gg.

But you can call her Adomin ~☆！

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Slash Commands](#slash-commands)
  - [Event Commands](#event-commands)
  - [Registration Commands](#registration-commands)
  - [Check-In Commands](#check-in-commands)
  - [Setup Commands](#setup-commands)
  - [Help Commands](#help-commands)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Infrastructure](#infrastructure)
- [CI/CD](#cicd)
- [Contributing](#contributing)
  - [Adding Commands in Code](#adding-commands-in-code)
  - [Registering Commands with Discord](#registering-commands-with-discord)
  - [Adding AWS Services](#adding-aws-services)
- [Testing](#testing)

---

## Overview

Adomi-san is a serverless Discord bot running on AWS Lambda. It manages the full lifecycle of netplay bracket events — from creation and participant import via start.gg, to registration, check-in, and role cleanup when events end.

**Key features:**
- Create events manually or by importing from a [start.gg](https://start.gg) tournament
- Manage participant registration with per-event role assignment
- Check-in flow that assigns Discord roles automatically
- Server-wide organizer role gating for all management commands
- Automatic event cleanup via a scheduled poller Lambda

---

## Architecture

```
Discord HTTP POST
       │
       ▼
API Gateway (HTTP)
       │
       ▼
Lambda: lambda_handler.py  ──── Verifies Discord signature (PyNaCl)
       │
       ▼
bot.py  ──── Routes command name → handler function (via command_map.py)
       │
       ├── DynamoDB (event & server config data)
       └── SQS (async role removal queue)

EventBridge (every 15 min)
       │
       ▼
Lambda: jobs/event_poller/handler.py
       │
       ├── Scans DynamoDB for active events
       ├── Checks Discord Guild Scheduled Events for completion/cancellation
       ├── Queues SQS messages to remove participant roles
       └── Deletes completed event records from DynamoDB
```

**Stack:**
- Runtime: Python 3.11
- Hosting: AWS Lambda + API Gateway v2
- Database: DynamoDB (pay-per-request)
- Queue: SQS (async role removals)
- Secrets: AWS Secrets Manager (start.gg API token)
- IaC: Terraform (HCP Terraform Cloud)
- CI/CD: GitHub Actions

---

## Slash Commands

> Organizer role is configured per-server using `/setup-server`. Most management commands require it.

### Event Commands

These commands manage the lifecycle of events on your server. All require the **organizer role**.

| Command | Description |
|---------|-------------|
| `/event-create` | Create a new event manually |
| `/event-update` | Update an existing event's details |
| `/event-delete` | Delete an event |
| `/event-create-startgg` | Create an event by importing data from a start.gg tournament link |
| `/event-update-startgg` | Link an existing event to a start.gg tournament and import participants |
| `/event-refresh-startgg` | Re-sync the registered participant list from start.gg |
| `/event-list` | List all active events on the server |

**`/event-create` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Display name for the event |
| `event_location` | string | yes | Venue or location |
| `start_time` | string | yes | Start time (e.g. `2026-03-19 19:30`) |
| `end_time` | string | yes | End time |
| `timezone` | string | yes | Timezone (autocomplete) |
| `event_description` | string | no | Optional description |
| `participant_role` | role | no | Role to assign on check-in; falls back to server default if omitted |

**`/event-update` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to update (autocomplete) |
| `new_name` | string | no | Rename the event |
| `event_location` | string | no | Update location |
| `start_time` | string | no | Update start time |
| `end_time` | string | no | Update end time |
| `timezone` | string | no | Timezone for the new time values |
| `event_description` | string | no | Update description |
| `participant_role` | role | no | Update participant role |

**`/event-delete` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to delete (autocomplete) |

**`/event-create-startgg` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_link` | string | yes | start.gg event URL (e.g. `https://www.start.gg/tournament/my-tourney/event/main-bracket`) |
| `end_time` | string | yes | End time (start.gg does not provide this) |
| `timezone` | string | yes | Timezone for end time (autocomplete) |
| `participant_role` | role | no | Role to assign on check-in |

**`/event-update-startgg` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to update (autocomplete) |
| `event_link` | string | yes | start.gg event URL |
| `end_time` | string | yes | End time |
| `timezone` | string | yes | Timezone for end time |
| `participant_role` | role | no | Role to assign on check-in |

**`/event-refresh-startgg` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to refresh (autocomplete) |

---

### Registration Commands

These commands manage who is registered for an event.

| Command | Who can use | Description |
|---------|-------------|-------------|
| `/register` | Any user (organizer can register others) | Register for an event |
| `/register-list` | Organizer | List all registered participants |
| `/register-remove` | Organizer | Remove a user from registration |
| `/register-clear` | Organizer | Clear the entire registration list |
| `/register-toggle` | Organizer | Open or close registration for an event |

**`/register` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to register for (autocomplete) |
| `user` | user | no | Register another user (organizer only) |

**`/register-list` / `/register-clear` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |

**`/register-remove` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |
| `user` | user | yes | User to remove |

**`/register-toggle` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |
| `state` | choice | yes | `Start` (open) or `End` (close) |

---

### Check-In Commands

These commands manage the check-in flow. Checking in assigns the event's participant role to the user.

| Command | Who can use | Description |
|---------|-------------|-------------|
| `/check-in` | Any registered user | Check in and receive participant role |
| `/check-in-list` | Organizer | List all checked-in participants |
| `/check-in-clear` | Organizer | Clear check-ins and remove participant roles |
| `/check-in-list-absent` | Organizer | List registered users who have not checked in |
| `/check-in-toggle` | Organizer | Open or close check-ins for an event |

**`/check-in` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to check into (autocomplete) |

**`/check-in-list` / `/check-in-clear` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |

**`/check-in-list-absent` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |
| `ping_users` | boolean | no | Mention absent users in the response |

**`/check-in-toggle` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Target event (autocomplete) |
| `state` | choice | yes | `Start` (open) or `End` (close) |

---

### Setup Commands

These commands configure the bot for your server. All require the **Manage Server** Discord permission.

| Command | Description |
|---------|-------------|
| `/setup-server` | Initialize server configuration with an organizer role |
| `/set-organizer-role` | Update the organizer role |
| `/set-default-participant-role` | Set the default role assigned to participants on check-in |
| `/show-event-roles` | Display the participant role configured for a specific event |

**`/setup-server` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organizer_role` | role | yes | Role that grants access to management commands |

**`/set-organizer-role` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `organizer_role` | role | yes | New organizer role |

**`/set-default-participant-role` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `participant_role` | role | yes | Default role to assign on check-in when no event-specific role is set |

**`/show-event-roles` parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event to inspect (autocomplete) |

> **Participant role resolution order:** event-specific role (set at creation/update) → server default (`/set-default-participant-role`) → none (warning shown)

---

### Help Commands

| Command | Description |
|---------|-------------|
| `/help` | General help overview |
| `/help-event` | Help for event commands |
| `/help-register` | Help for registration commands |
| `/help-check-in` | Help for check-in commands |

---

## Database Schema

**DynamoDB table:** `adomi-discord-server-data-{env}`
- Billing: Pay-per-request
- Partition key (`PK`): `SERVER#{server_id}`
- Sort key (`SK`): `CONFIG` or `EVENT#{event_id}`

**Global Secondary Index — `EventNameIndex`:**
- Partition key: `server_id`
- Sort key: `event_name`
- Projected attributes: `event_id`, `start_time`, `end_time`, `description`
  (used for autocomplete and event poller scans)

### ServerConfig record (SK: `CONFIG`)

| Field | Description |
|-------|-------------|
| `server_id` | Discord guild ID |
| `organizer_role` | Role ID for organizers |
| `default_participant_role` | Default role assigned on check-in (optional) |

### EventData record (SK: `EVENT#{event_id}`)

| Field | Description |
|-------|-------------|
| `server_id` | Parent guild ID |
| `event_id` | Auto-generated unique identifier |
| `event_name` | Display name |
| `event_location` | Venue or location string |
| `start_time` | ISO 8601 UTC timestamp |
| `end_time` | ISO 8601 UTC timestamp (used as cleanup deadline by the event poller) |
| `participant_role` | Role ID assigned on check-in |
| `check_in_enabled` | Boolean — whether check-in is open |
| `register_enabled` | Boolean — whether registration is open |
| `registered` | Map of `user_id → {display_name, user_id, time_added, source}` |
| `checked_in` | Map of `user_id → {display_name, user_id, check_in_time}` |
| `queue` | Reserved (unused) |
| `startgg_url` | start.gg event link (optional) |
| `start_message` | Custom start message (optional) |
| `end_message` | Custom end message (optional) |

---

## Configuration

[config.env](./config.env) is the single source of truth for non-secret configuration. Values are read into GitHub Actions environment variables and passed to Terraform as variables during deployment.

| Variable | Description |
|----------|-------------|
| `APP_NAME` | Lambda function name prefix |
| `SQS_WORKER_NAME` | SQS queue name for role removal |
| `EVENT_POLLER_NAME` | Event poller Lambda name prefix |
| `AWS_REGION` | AWS deployment region |
| `PYTHON_RUNTIME` | Python version for Lambda |
| `HCP_TERRAFORM_ORG` | HCP Terraform organization |
| `HCP_TERRAFORM_PROJECT` | HCP Terraform project |
| `HCP_TERRAFORM_WORKSPACE_DEV` | Dev Terraform workspace |
| `HCP_TERRAFORM_WORKSPACE_PROD` | Prod Terraform workspace |
| `DISCORD_PUBLIC_KEY_DEV` | Discord bot public key (dev) |
| `DISCORD_PUBLIC_KEY_PROD` | Discord bot public key (prod) |

**Secrets** (stored in GitHub Actions secrets, not in config.env):
- `DISCORD_BOT_TOKEN_DEV` / `DISCORD_BOT_TOKEN_PROD`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `TF_TOKEN` (HCP Terraform API token)
- `STARTGG_API_TOKEN` (stored in AWS Secrets Manager at runtime)

**Lambda environment variables** (injected by Terraform):
- `REGION`
- `PUBLIC_KEY`
- `DISCORD_BOT_TOKEN`
- `DYNAMODB_TABLE_NAME`
- `REMOVE_ROLE_QUEUE_URL`
- `STARTGG_SECRET_NAME`

Reading config in code: [src/constants.py](./src/constants.py)

---

## Infrastructure

Terraform modules live in [terraform/](./terraform/), split into two independent root modules.

### `terraform/infra/`

Provisions the main bot infrastructure:

- **Lambda** (`{APP_NAME}-{env}`) — handles Discord HTTP interactions
  - Handler: `lambda_handler.lambda_handler`
  - Timeout: 10 seconds
  - Layers: PyNaCl + application dependencies (built and uploaded by CI)
- **API Gateway v2** — HTTP API with a `POST /{APP_NAME}` route, proxied to Lambda
- **DynamoDB table** — `adomi-discord-server-data-{env}`
- **SQS queue** — `{SQS_WORKER_NAME}` for async role removals
- **Secrets Manager** — `startgg_api_token`
- **IAM roles** — separate roles for the main Lambda and the SQS worker

### `terraform/event_poller/`

Provisions the scheduled cleanup job:

- **Lambda** (`{EVENT_POLLER_NAME}-{env}`) — scans for ended events and cleans up
  - Handler: `handler.handler`
  - Timeout: 60 seconds
  - Layers: application dependencies
- **EventBridge rule** — triggers every 15 minutes
- **IAM role** — scoped to DynamoDB reads, SQS sends, and Discord API calls

### Adding new infrastructure

1. Add config variables to [config.env](./config.env) and [terraform/infra/variables.tf](./terraform/infra/variables.tf)
2. Update the `read-config` step in [.github/workflows/development.yml](./.github/workflows/development.yml) to pass new vars
3. Reference them in Lambda environment variables via Terraform
4. Read them in Python via [src/constants.py](./src/constants.py)

---

## CI/CD

### `development.yml` — Deploy to dev (push to any non-main branch)

1. **read-config** — parse `config.env` into environment variables
2. **unit-test** — run `pytest tests/`
3. **deploy** — build Lambda layers, package source, upload to S3, apply Terraform (dev workspace)
4. **register-commands** *(manual trigger only)* — register slash commands with Discord

### `release.yml` — Deploy to prod (tag push to main)

Same steps as development but targets the prod Terraform workspace and prod Discord bot token.

### `workflow-register-commands.yml` — Register slash commands

Manually triggered via GitHub Actions `workflow_dispatch`. Accepts a command name (or `all`) and calls Discord's API to register/update slash command definitions.

### `workflow-run-unit-tests.yml` — Run unit tests (reusable)

Called by other workflows. Sets up a venv, installs dependencies, and runs `pytest tests/`.

---

## Contributing

### Adding Commands in Code

The [commands/](./src/commands/) directory is organized by command group. Create a directory for the set of commands you are working on, or find the existing directory and add to it.

[command_map.py](./src/commands/command_map.py) merges `CommandMapping` dicts from each group's `mapping.py` to build the full command registry.

Example mapping entry:

```python
"command-name": {                          # kebab-case is standard for Discord
    "function": commands.my_command,       # function reference
    "description": "Describe the command",
    "params": [
        CommandParam(
            name="param_name",             # snake_case is standard
            description="Param description",
            param_type=AppCommandOptionType.boolean,
            required=False,
            choices=[
                ParamChoice(name="Yes", value=True),
                ParamChoice(name="No", value=False),
            ]
        )
    ]
}
```

For autocomplete on a parameter, add an `autocomplete_handler` key alongside the command entry. See existing event command mappings for examples.

For more details, see the [commands/models/](./src/commands/models/) directory.

### Registering Commands with Discord

**Run the "Register Discord Bot Slash Commands" workflow via GitHub Actions `workflow_dispatch`** to register new or updated commands with Discord.

Provide the command name to register (must match the key in the Python mapping), or `all` to re-register everything. The [register_commands script](./scripts/register_commands.py) discovers commands via `command_map.py` and calls Discord's API.

### Adding AWS Services

Most commands only need DynamoDB. If you need an additional service (e.g. a new SQS queue), add it to [AWSServices](./src/aws_services.py), which is passed as a parameter to every command handler.

This pattern allows AWS connections to be initialized once on Lambda startup (minimizing cold start impact) and mocked cleanly in tests.

> **Note:** Discord requires a response within **3 seconds**. For slow operations, use deferred responses or offload work to SQS/another Lambda.

---

## Testing

### Unit Tests

Unit tests live in [tests/](./tests/) and mirror the source structure. They are code sanity tests — the primary testing path is integration testing through the live bot.

Make a practice of adding at least basic unit tests when adding new commands or changing existing behavior.

### Running Tests Locally

```bash
make test
```

Or manually:

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # macOS/Linux
   # .venv\Scripts\activate         # Windows
   ```

2. Install dependencies:
   ```bash
   pip install setuptools
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. Set `PYTHONPATH`:
   ```bash
   export PYTHONPATH="$PYTHONPATH:$(pwd)/src"
   # Windows: $env:PYTHONPATH="$env:PYTHONPATH;${PWD}\src"
   ```

4. Run tests:
   ```bash
   pytest tests/
   ```
