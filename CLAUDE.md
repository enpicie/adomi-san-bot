# CLAUDE.md

## Project

Adomi-san — serverless Discord bot for start.gg netplay bracket management (events, registration, check-in, score reporting, leagues).

Initialized retroactively against: spec-general.md + spec-coding-general.md + spec-platform-cicd.md (see [specs/](./specs/)).

## Stack

- **Python 3.12** — Lambda runtime; single language across bot, jobs, and scripts.
- **AWS Lambda + API Gateway v2** — serverless HTTP entry point for Discord interactions; zero idle cost.
- **DynamoDB** (single table, pay-per-request) — all server/event/league state; no relational needs at this scale.
- **SQS** — async role removal and sheets-agent work; keeps slash-command responses under Discord's 3-second limit.
- **Secrets Manager** — start.gg API token, OAuth secret, Google Sheets service account credentials at runtime.
- **EventBridge** — 15-minute schedule driving the cleanup/reminder poller Lambda.
- **Terraform (S3 remote state via org composite action)** — two independent roots; state keyed per project/env.
- **GitHub Actions** — dev pipeline on non-main pushes, release pipeline on version tags.

## Structure

```
src/                      # Main bot Lambda (Discord interactions)
  lambda_handler.py       # Entry point — Discord signature verification FIRST
  bot.py                  # Dispatches command name → handler via command_map
  commands/<group>/       # One directory per command group
    mapping.py            # Group's CommandMapping dict (self-discovery)
  commands/command_map.py # Merges every group's mapping.py into the registry
  database/               # DynamoDB access + dataclass models
jobs/<name>/              # Independent Lambda zips (remove_role, scheduled_job,
                          # startgg_oauth, sheets_agent). CANNOT import src/ —
                          # shared logic is duplicated with MIRROR comments.
terraform/infra/          # Root module: bot Lambda, API GW, DynamoDB, SQS,
                          # secrets, sheets agent, OAuth callback
terraform/scheduled_job/  # Root module: EventBridge-scheduled poller Lambda
scripts/                  # Operational scripts (Discord command registration)
tests/                    # pytest unit tests, mirror source layout
specs/                    # Platform specs this repo conforms to
.platform/                # Gitignored architecture docs (audit, data model, scaling)
```

## Security Rules — Non-Negotiable

- No secret literals anywhere in code, config, comments, or tests.
- Secrets come only from environment variables or AWS Secrets Manager.
- Never log tokens, secrets, or full request/response payloads.
- PII stays out of logs — reference users/servers by ID only.
- Discord signature verification (PyNaCl) must remain the FIRST thing `lambda_handler` does. Never reorder, weaken, or bypass it.

## Conventions

The Code Style rules at the bottom of this file (imports, Discord mentions, logging) are binding. In addition:

- **Import carve-out:** Classes, dataclasses, exceptions, and TypedDicts MAY be from-imported; functions/constants of internal modules must use module-alias imports.
- **Command self-discovery:** to add a command group, create `src/commands/<group>/mapping.py` with the group's `CommandMapping` dict and merge it in `src/commands/command_map.py`. Register with Discord via the register-commands workflow.
- **Jobs are self-contained:** `jobs/<name>/` packages cannot import from `src/`. When logic must exist in both places, duplicate it and mark both copies with a MIRROR comment; never import across the boundary.

## Do Not Modify Without Explicit Instruction

- `src/commands/command_map.py` merge mechanism (command self-discovery depends on it)
- `.github/workflows/` deploy plumbing (workflow-deploy.yml inputs/tf_vars wiring)
- Terraform state keys (`state_key:` values in workflow-deploy.yml)
- `config.env` values (resolved deployment values — changing them renames live AWS resources)

## Design Standards

N/A — no UI surface; Discord renders all output.

## Deeper Context

- `.platform/audit.md` — platform-spec conformance audit findings
- `.platform/data-model.md` — full entity list, PK/SK scheme, GSIs, relationships
- `.platform/scaling-plan.md` — thresholds, staging decision, cost tiers
- `docs/` — architecture and contributing guides
- `specs/` — the platform specs this repo is held against

---

# Code Style

## Imports

Import modules as aliases rather than importing individual functions. This keeps call sites readable — readers can trace methods back to their source without hunting through import lists.

**Do:**
```python
import commands.schedule.schedule_helper as schedule_helper
schedule_helper.sync_schedule(...)
```

**Don't:**
```python
from commands.schedule.schedule_helper import sync_schedule, remove_schedule_event
sync_schedule(...)
```

This applies to all internal modules (helpers, utils, db, etc.).

## Discord Mentions

Use `message_helper` for all Discord mention/ping formatting. Never inline the raw Discord syntax manually.

| Mention type | Use |
|---|---|
| User ping | `message_helper.get_user_ping(user_id)` → `<@id>` |
| Channel mention | `message_helper.get_channel_mention(channel_id)` → `<#id>` |
| Role ping | `message_helper.get_role_ping(role_id)` → `<@&id>` |

**Don't:**
```python
f"<@{user_id}>"
f"<#{channel_id}>"
f"<@&{role_id}>"
```

## Logging

**`src/` code** uses `print` with a `[name]` prefix identifying the subsystem. The name must match the module's domain and be consistent within that file.

```python
print(f"[db] GET EVENT server={server_id} event_id={event_id}")
print(f"[discord] POST /guilds/{guild_id}/scheduled-events | name={name!r}")
print(f"[schedule] Failed to update schedule message for server {server_id}")
print(f"[event] Created event_id={event_id} name={name!r} server={server_id}")
```

**`jobs/` code** uses the standard `logger` (`logging.getLogger()`) — no plain `print`.

Never use a bare `print(...)` without the `[name]` prefix in `src/`, and never use `print` at all in `jobs/`.
