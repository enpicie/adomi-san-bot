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
  - [Score Reporting Commands](#score-reporting-commands)
  - [Schedule Commands](#schedule-commands)
  - [League Commands](#league-commands)
  - [Help Commands](#help-commands)
- [Scheduled Job Flows](#scheduled-job-flows)
  - [Event Cleanup](#event-cleanup)
  - [Event Reminders](#event-reminders)
  - [Schedule Sync](#schedule-sync)
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

Message `@enpicie` on Discord or Twitter/X if you are interested in adding Adomin to your server.

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

| Command                  | Description                                                             |
| ------------------------ | ----------------------------------------------------------------------- |
| `/event-create`          | Create a new event manually                                             |
| `/event-update`          | Update an existing event's details                                      |
| `/event-delete`          | Delete an event                                                         |
| `/event-create-startgg`  | Create an event by importing data from a start.gg tournament link       |
| `/event-update-startgg`  | Link an existing event to a start.gg tournament and import participants |
| `/event-refresh-startgg` | Re-sync the registered participant list from start.gg                   |
| `/event-list`            | List all active events on the server                                    |

**`/event-create` parameters:**

| Parameter           | Type   | Required | Description                                                         |
| ------------------- | ------ | -------- | ------------------------------------------------------------------- |
| `event_name`        | string | yes      | Display name for the event                                          |
| `event_location`    | string | yes      | Venue or location                                                   |
| `start_time`        | string | yes      | Start time (e.g. `2026-03-19 19:30`)                                |
| `end_time`          | string | yes      | End time                                                            |
| `timezone`          | string | yes      | Timezone (autocomplete)                                             |
| `event_description` | string | no       | Optional description                                                |
| `participant_role`  | role   | no       | Role to assign on check-in; falls back to server default if omitted |

**`/event-update` parameters:**

| Parameter           | Type   | Required | Description                      |
| ------------------- | ------ | -------- | -------------------------------- |
| `event_name`        | string | yes      | Event to update (autocomplete)   |
| `new_name`          | string | no       | Rename the event                 |
| `event_location`    | string | no       | Update location                  |
| `start_time`        | string | no       | Update start time                |
| `end_time`          | string | no       | Update end time                  |
| `timezone`          | string | no       | Timezone for the new time values |
| `event_description` | string | no       | Update description               |
| `participant_role`  | role   | no       | Update participant role          |

**`/event-delete` parameters:**

| Parameter    | Type   | Required | Description                    |
| ------------ | ------ | -------- | ------------------------------ |
| `event_name` | string | yes      | Event to delete (autocomplete) |

**`/event-create-startgg` parameters:**

| Parameter          | Type   | Required | Description                                                                               |
| ------------------ | ------ | -------- | ----------------------------------------------------------------------------------------- |
| `event_link`       | string | yes      | start.gg event URL (e.g. `https://www.start.gg/tournament/my-tourney/event/main-bracket`) |
| `end_time`         | string | yes      | End time (start.gg does not provide this)                                                 |
| `timezone`         | string | yes      | Timezone for end time (autocomplete)                                                      |
| `participant_role` | role   | no       | Role to assign on check-in                                                                |

**`/event-update-startgg` parameters:**

| Parameter          | Type   | Required | Description                    |
| ------------------ | ------ | -------- | ------------------------------ |
| `event_name`       | string | yes      | Event to update (autocomplete) |
| `event_link`       | string | yes      | start.gg event URL             |
| `end_time`         | string | yes      | End time                       |
| `timezone`         | string | yes      | Timezone for end time          |
| `participant_role` | role   | no       | Role to assign on check-in     |

**`/event-refresh-startgg` parameters:**

| Parameter    | Type   | Required | Description                     |
| ------------ | ------ | -------- | ------------------------------- |
| `event_name` | string | yes      | Event to refresh (autocomplete) |

---

### Registration Commands

These commands manage who is registered for an event.

| Command            | Who can use                              | Description                             |
| ------------------ | ---------------------------------------- | --------------------------------------- |
| `/register`        | Any user (organizer can register others) | Register for an event                   |
| `/register-list`   | Organizer                                | List all registered participants        |
| `/register-remove` | Organizer                                | Remove a user from registration         |
| `/register-clear`  | Organizer                                | Clear the entire registration list      |
| `/register-toggle` | Organizer                                | Open or close registration for an event |

**`/register` parameters:**

| Parameter    | Type   | Required | Description                            |
| ------------ | ------ | -------- | -------------------------------------- |
| `event_name` | string | yes      | Event to register for (autocomplete)   |
| `user`       | user   | no       | Register another user (organizer only) |

**`/register-list` / `/register-clear` parameters:**

| Parameter    | Type   | Required | Description                 |
| ------------ | ------ | -------- | --------------------------- |
| `event_name` | string | yes      | Target event (autocomplete) |

**`/register-remove` parameters:**

| Parameter    | Type   | Required | Description                 |
| ------------ | ------ | -------- | --------------------------- |
| `event_name` | string | yes      | Target event (autocomplete) |
| `user`       | user   | yes      | User to remove              |

**`/register-toggle` parameters:**

| Parameter    | Type   | Required | Description                     |
| ------------ | ------ | -------- | ------------------------------- |
| `event_name` | string | yes      | Target event (autocomplete)     |
| `state`      | choice | yes      | `Start` (open) or `End` (close) |

---

### Check-In Commands

These commands manage the check-in flow. Checking in assigns the event's participant role to the user.

| Command                 | Who can use         | Description                                   |
| ----------------------- | ------------------- | --------------------------------------------- |
| `/check-in`             | Any registered user | Check in and receive participant role         |
| `/check-in-list`        | Organizer           | List all checked-in participants              |
| `/check-in-clear`       | Organizer           | Clear check-ins and remove participant roles  |
| `/check-in-list-absent` | Organizer           | List registered users who have not checked in |
| `/check-in-toggle`      | Organizer           | Open or close check-ins for an event          |

**`/check-in` parameters:**

| Parameter    | Type   | Required | Description                        |
| ------------ | ------ | -------- | ---------------------------------- |
| `event_name` | string | yes      | Event to check into (autocomplete) |

**`/check-in-list` / `/check-in-clear` parameters:**

| Parameter    | Type   | Required | Description                 |
| ------------ | ------ | -------- | --------------------------- |
| `event_name` | string | yes      | Target event (autocomplete) |

**`/check-in-list-absent` parameters:**

| Parameter    | Type    | Required | Description                          |
| ------------ | ------- | -------- | ------------------------------------ |
| `event_name` | string  | yes      | Target event (autocomplete)          |
| `ping_users` | boolean | no       | Mention absent users in the response |

**`/check-in-toggle` parameters:**

| Parameter    | Type   | Required | Description                     |
| ------------ | ------ | -------- | ------------------------------- |
| `event_name` | string | yes      | Target event (autocomplete)     |
| `state`      | choice | yes      | `Start` (open) or `End` (close) |

---

### Setup Commands

These commands configure the bot for your server. All require the **Manage Server** Discord permission.

| Command                         | Description                                                  |
| ------------------------------- | ------------------------------------------------------------ |
| `/setup-server`                 | Initialize server configuration with an organizer role       |
| `/set-organizer-role`           | Update the organizer role                                    |
| `/set-default-participant-role` | Set the default role assigned to participants on check-in    |
| `/show-event-roles`             | Display the participant role configured for a specific event |

**`/setup-server` parameters:**

| Parameter        | Type | Required | Description                                    |
| ---------------- | ---- | -------- | ---------------------------------------------- |
| `organizer_role` | role | yes      | Role that grants access to management commands |

**`/set-organizer-role` parameters:**

| Parameter        | Type | Required | Description        |
| ---------------- | ---- | -------- | ------------------ |
| `organizer_role` | role | yes      | New organizer role |

**`/set-default-participant-role` parameters:**

| Parameter          | Type | Required | Description                                                           |
| ------------------ | ---- | -------- | --------------------------------------------------------------------- |
| `participant_role` | role | yes      | Default role to assign on check-in when no event-specific role is set |

**`/show-event-roles` parameters:**

| Parameter    | Type   | Required | Description                     |
| ------------ | ------ | -------- | ------------------------------- |
| `event_name` | string | yes      | Event to inspect (autocomplete) |

> **Participant role resolution order:** event-specific role (set at creation/update) → server default (`/set-default-participant-role`) → none (warning shown)

---

### Score Reporting Commands

These commands allow participants to report bracket set results directly to start.gg.

> **Prerequisites:**
>
> - An organizer must run `/startgg-connect` to link their start.gg account to the server before score reporting is available.
> - Participants must have their start.gg account linked to Discord in their start.gg account settings under **Connections**. Users without a linked account cannot be looked up and score reporting will fail for them.

| Command                    | Who can use     | Description                                                          |
| -------------------------- | --------------- | -------------------------------------------------------------------- |
| `/startgg-connect`         | Organizer       | Link a start.gg organizer account to this server via OAuth           |
| `/startgg-report-score`    | Any participant | Report the result of a start.gg bracket set                          |
| `/startgg-notify-unlinked` | Organizer       | List start.gg participants who have not linked their Discord account |

#### `/startgg-connect`

Initiates the start.gg OAuth flow for the server. The organizer who runs this command must have tournament manager permissions on start.gg for the tournaments they want to report scores on — score reporting is performed on their behalf using their linked account.

Running the command returns a one-time authorization link (expires in 10 minutes). After the organizer approves access on start.gg, the account is linked to the server and `/startgg-report-score` becomes available. Only one account can be linked to a server at a time; running `/startgg-connect` again replaces the previous link.

No parameters.

#### `/startgg-report-score`

**`/startgg-report-score` parameters:**

| Parameter    | Type   | Required | Description                                                |
| ------------ | ------ | -------- | ---------------------------------------------------------- |
| `event_name` | string | yes      | Event the set belongs to (autocomplete)                    |
| `winner`     | user   | yes      | Player who won the set                                     |
| `loser`      | user   | yes      | Player who lost the set                                    |
| `score`      | string | yes      | Score in `<winner games>-<loser games>` format, e.g. `2-1` |

The command finds the most recently created open set between the two players on start.gg and reports the result. Both players must be registered for the event via start.gg with Discord linked.

#### `/startgg-notify-unlinked`

**`/startgg-notify-unlinked` parameters:**

| Parameter    | Type   | Required | Description                   |
| ------------ | ------ | -------- | ----------------------------- |
| `event_name` | string | yes      | Event to check (autocomplete) |

Fetches the current entrant list from start.gg and returns all participants who do not have a Discord account linked. The response lists their start.gg gamerTags and instructs them to go to their start.gg profile → **Edit Profile** → **Connections** → connect Discord and enable **Display on profile**.

---

### Schedule Commands

These commands manage a persistent schedule message in a Discord channel listing upcoming events. All require the **organizer role**.

| Command                | Description                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------- |
| `/schedule-post`       | Post a new tracked schedule message in a channel                                   |
| `/schedule-update`     | Refresh the tracked message, optionally changing the title                         |
| `/schedule-plan-event` | Add a planned event placeholder to the schedule before creating it as a real event |
| `/schedule-plan-remove`| Remove a planned event placeholder                                                 |

The bot tracks one schedule message per server (`schedule_channel_id` + `schedule_message_id` in `ServerConfig`). The message is a single living post that gets edited in place rather than reposted.

**Message format:**

```
# Title

- [Upcoming Event](https://start.gg/...) - **<t:1234567890:F>**
- _Planned Event - **<t:1234567891:F>**_
- ~~Past Event - **<t:1234567889:F>**~~
```

- Events linked to start.gg are rendered as markdown hyperlinks.
- Planned events (added via `/schedule-plan-event`) are rendered in *italics*.
- Past events (start time in the past) are rendered with ~~strikethrough~~.
- All entries are sorted by start time, earliest first.

**Title persistence:** The title is stored in the message itself (`# Title` on the first line). Auto-updates extract it from the current message content, so it persists across syncs without being stored in the database. Use `/schedule-update new_title:...` to change it.

**Planned event auto-removal:** When a real event is created via `/event-create` or `/event-create-startgg` with a name that case-insensitively matches an existing plan, the plan is automatically removed and the schedule is refreshed immediately.

**`/schedule-post` parameters:**

| Parameter        | Type    | Required | Description                                                         |
| ---------------- | ------- | -------- | ------------------------------------------------------------------- |
| `channel`        | channel | no*      | Channel to post the schedule in (*required when creating a new post)|
| `title`          | string  | no       | Header text for the schedule (default: `Upcoming Events`)           |
| `create_new_post`| boolean | no       | Force a new post even if a tracked message already exists           |

**`/schedule-update` parameters:**

| Parameter   | Type   | Required | Description                                            |
| ----------- | ------ | -------- | ------------------------------------------------------ |
| `new_title` | string | no       | New header text (leave blank to keep the current title)|

**`/schedule-plan-event` parameters:**

| Parameter    | Type   | Required | Description                                                                     |
| ------------ | ------ | -------- | ------------------------------------------------------------------------------- |
| `name`       | string | yes      | Name of the planned event — must match the name used in `/event-create` exactly |
| `start_time` | string | yes      | Format: `2026-03-19 19:30` (24-hour time)                                       |
| `timezone`   | string | yes      | Timezone for the start time (autocomplete)                                      |
| `event_link` | string | no       | Optional link (e.g. start.gg registration page)                                 |

**`/schedule-plan-remove` parameters:**

| Parameter   | Type   | Required | Description                              |
| ----------- | ------ | -------- | ---------------------------------------- |
| `plan_name` | string | yes      | Plan to remove (autocomplete)            |

---

### League Commands

League commands manage long-running competitive leagues tracked via Google Sheets. Participant data (status, name, Discord ID) lives in a Google Sheet tab that the bot reads and writes.

> **Prerequisite:** The league's Google Sheet must be shared (with **Editor** access) to the bot's service account email. Run `/league-view` to see the configured service account address.

| Command                     | Who can use                           | Description                                                               |
| --------------------------- | ------------------------------------- | ------------------------------------------------------------------------- |
| `/league-create`            | Organizer                             | Create a new league record                                                |
| `/league-update`            | Organizer                             | Update an existing league's name, sheet link, or participant role         |
| `/league-list`              | Organizer                             | List all leagues for this server                                          |
| `/league-view`              | Organizer                             | View details of a specific league                                         |
| `/league-setup`             | Organizer                             | Initialize (or re-apply styling to) the Participants sheet                |
| `/league-delete`            | Organizer                             | Delete a league record                                                    |
| `/league-join-toggle`       | Organizer                             | Open or close joining for a league                                        |
| `/league-report-toggle`     | Organizer                             | Open or close score reporting for a league                                |
| `/league-sync-participants` | Organizer                             | Sync active participants from the sheet, assigning/removing Discord roles |
| `/league-join`              | Any user                              | Join a league — adds you to the Participants sheet                        |
| `/league-report-score`      | Any user                              | Report the result of a league match and update the score sheet            |
| `/league-deactivate`        | Any user (organizer to target others) | Mark yourself (or another player) as inactive or DNF                      |

**`/league-create` parameters:**

| Parameter                 | Type   | Required | Description                                           |
| ------------------------- | ------ | -------- | ----------------------------------------------------- |
| `league_name`             | string | yes      | Display name for the league                           |
| `league_id`               | string | yes      | Short unique identifier (max 4 characters, e.g. `S1`) |
| `google_sheets_link`      | string | yes      | Link to the Google Sheet tracking this league         |
| `active_participant_role` | string | no       | Role ID to assign to active participants              |

**`/league-update` parameters:**

| Parameter                 | Type   | Required | Description                    |
| ------------------------- | ------ | -------- | ------------------------------ |
| `league_id`               | string | yes      | ID of the league to update     |
| `league_name`             | string | no       | New display name               |
| `google_sheets_link`      | string | no       | New Google Sheets link         |
| `active_participant_role` | string | no       | New active participant role ID |

**`/league-view` / `/league-setup` / `/league-delete` / `/league-join` / `/league-sync-participants` parameters:**

| Parameter     | Type   | Required | Description                     |
| ------------- | ------ | -------- | ------------------------------- |
| `league_name` | string | yes      | League to target (autocomplete) |

**`/league-join-toggle` parameters:**

| Parameter     | Type   | Required | Description                                     |
| ------------- | ------ | -------- | ----------------------------------------------- |
| `league_name` | string | yes      | League to target (autocomplete)                 |
| `state`       | choice | yes      | `Start` (open joining) or `End` (close joining) |

**`/league-report-toggle` parameters:**

| Parameter     | Type   | Required | Description                                              |
| ------------- | ------ | -------- | -------------------------------------------------------- |
| `league_name` | string | yes      | League to target (autocomplete)                          |
| `state`       | choice | yes      | `Start` (open score reporting) or `End` (close it)       |

**`/league-report-score` parameters:**

| Parameter     | Type   | Required | Description                                                                 |
| ------------- | ------ | -------- | --------------------------------------------------------------------------- |
| `league_name` | string | yes      | League to target (autocomplete)                                             |
| `winner`      | user   | yes      | Player who won the match                                                    |
| `loser`       | user   | yes      | Player who lost the match                                                   |
| `score`       | string | yes      | Score in `<winner games>-<loser games>` format, e.g. `3-2` (winner first)  |

Score reporting must be enabled by an organizer via `/league-report-toggle` before participants can submit results.

**`/league-deactivate` parameters:**

| Parameter     | Type    | Required | Description                                           |
| ------------- | ------- | -------- | ----------------------------------------------------- |
| `league_name` | string  | yes      | League to target (autocomplete)                       |
| `dnf`         | boolean | no       | Set `True` to mark as **DNF** instead of **INACTIVE** |
| `player`      | user    | no       | (Organizers only) Target player to deactivate         |

Participant statuses in the sheet: **QUEUED** (joined, pending), **ACTIVE** (active participant), **INACTIVE** (stepped down, can re-queue), **DNF** (did not finish — cannot re-join without organizer intervention).

When `/league-sync-participants` is run, any players newly marked **ACTIVE** in the sheet receive the configured Discord role; players no longer **ACTIVE** have the role queued for removal.

---

### Help Commands

| Command          | Description                                |
| ---------------- | ------------------------------------------ |
| `/help`          | General help overview                      |
| `/help-event`    | Help for event commands                    |
| `/help-register` | Help for registration commands             |
| `/help-check-in` | Help for check-in commands                 |
| `/help-startgg`  | Help for start.gg score reporting commands |
| `/help-league`   | Help for league management commands        |
| `/help-schedule` | Help for schedule commands                 |

---

## Scheduled Job Flows

The scheduled job (`jobs/scheduled_job/handler.py`) runs every 15 minutes via EventBridge. On each invocation it performs three passes in order.

### Event Cleanup

Scans `EventNameIndex` to get all tracked event IDs grouped by server. For each event, fetches the corresponding Discord Guild Scheduled Event status:

- **Completed (status 3) or Cancelled (status 4):** deletes the DynamoDB record and queues participant role removal.
- **Not found on Discord:** treats the event as ended and applies the same cleanup.
- **Active:** no cleanup; proceeds to reminder check.

After processing all events for a server, if any were cleaned up and a `notification_channel_id` is configured, a summary message is posted to that channel (optionally pinging the organizer role if `ping_organizers` is set).

### Event Reminders

For each active event, the job checks whether a 24-hour advance reminder should be sent. A reminder is sent when **all** of the following are true:

1. `should_post_reminder` is `True` on the event record
2. `did_post_reminder` is `False` (reminder has not already been sent)
3. The event's `start_time` falls within the next 24 hours
4. `announcement_channel_id` is configured on the server

Reminder message format:
```
@role 📣 **Event Name** is coming up <t:epoch:R> — starting <t:epoch:F>!
```

The role ping is omitted if `announcement_role_id` is not set. After a successful send, `did_post_reminder` is set to `True` to prevent duplicate reminders.

Configure reminder behavior per-server with `/setup-event-reminders`. Toggle per-event with the `announce_reminder` parameter on `/event-create` or `/event-update`.

### Schedule Sync

After cleanup and reminder processing for each server, the job syncs the tracked schedule message if one is configured (`schedule_message_id` is set in `ServerConfig`):

1. Fetches the current schedule message from Discord to extract the title from the first line (`# Title`).
2. Queries all real events and all `SCHEDULE_PLAN#` records for the server.
3. Removes any plan whose name case-insensitively matches a real event name.
4. Rebuilds the message content and edits the Discord message in place.

The sync only runs for servers that have active events (since the handler loops over servers from `EventNameIndex`). Servers with no active events but a configured schedule are not synced by the job — use `/schedule-post` or `/schedule-update` to manually refresh in that case.

---

## Database Schema

**DynamoDB table:** `adomi-discord-server-data-{env}`

- Billing: Pay-per-request
- Partition key (`PK`): `SERVER#{server_id}`
- Sort key (`SK`): `CONFIG`, `EVENT#{event_id}`, or `SCHEDULE_PLAN#{normalized_plan_name}`

**Global Secondary Index — `EventNameIndex`:**

- Partition key: `server_id`
- Sort key: `event_name`
- Projected attributes: `event_id`, `start_time`, `end_time`, `description`
  (used for autocomplete and event poller scans)

### ServerConfig record (SK: `CONFIG`)

| Field                      | Description                                                          |
| -------------------------- | -------------------------------------------------------------------- |
| `server_id`                | Discord guild ID                                                     |
| `organizer_role`           | Role ID for organizers                                               |
| `default_participant_role` | Default role assigned on check-in (optional)                         |
| `notification_channel_id`  | Channel to post bot notifications to (optional)                      |
| `ping_organizers`          | Whether to ping the organizer role in notifications (optional)       |
| `oauth_token_startgg`      | start.gg OAuth access token linked via `/startgg-connect` (optional) |
| `announcement_channel_id`  | Channel for event reminder announcements (optional)                  |
| `announcement_role_id`     | Role to ping in reminder announcements (optional)                    |
| `should_always_remind`     | Whether new events have reminders enabled by default (optional)      |
| `schedule_channel_id`      | Channel containing the tracked schedule message (optional)           |
| `schedule_message_id`      | Message ID of the tracked schedule message (optional)                |

### SchedulePlan record (SK: `SCHEDULE_PLAN#{normalized_name}`)

Planned event placeholders added via `/schedule-plan-event`. The SK key uses the plan name lowercased and stripped. Automatically deleted when a real event is created with a matching name.

| Field        | Description                                      |
| ------------ | ------------------------------------------------ |
| `plan_name`  | Display name of the planned event                |
| `start_time` | ISO 8601 UTC timestamp                           |
| `event_link` | Optional link (e.g. start.gg registration page) |

### EventData record (SK: `EVENT#{event_id}`)

| Field              | Description                                                           |
| ------------------ | --------------------------------------------------------------------- |
| `server_id`        | Parent guild ID                                                       |
| `event_id`         | Auto-generated unique identifier                                      |
| `event_name`       | Display name                                                          |
| `event_location`   | Venue or location string                                              |
| `start_time`       | ISO 8601 UTC timestamp                                                |
| `end_time`         | ISO 8601 UTC timestamp (used as cleanup deadline by the event poller) |
| `participant_role` | Role ID assigned on check-in                                          |
| `check_in_enabled` | Boolean — whether check-in is open                                    |
| `register_enabled` | Boolean — whether registration is open                                |
| `registered`       | Map of `user_id → {display_name, user_id, time_added, source}`        |
| `checked_in`       | Map of `user_id → {display_name, user_id, check_in_time}`             |
| `queue`            | Reserved (unused)                                                     |
| `startgg_url`          | start.gg event link (optional)                                            |
| `start_message`        | Custom start message (optional)                                           |
| `end_message`          | Custom end message (optional)                                             |
| `should_post_reminder` | Whether a 24-hour reminder announcement should be sent for this event     |
| `did_post_reminder`    | Whether the reminder has already been sent (prevents duplicate sends)     |

---

## Configuration

[config.env](./config.env) is the single source of truth for non-secret configuration. Values are read into GitHub Actions environment variables and passed to Terraform as variables during deployment.

| Variable                       | Description                     |
| ------------------------------ | ------------------------------- |
| `APP_NAME`                     | Lambda function name prefix     |
| `SQS_WORKER_NAME`              | SQS queue name for role removal |
| `EVENT_POLLER_NAME`            | Event poller Lambda name prefix |
| `AWS_REGION`                   | AWS deployment region           |
| `PYTHON_RUNTIME`               | Python version for Lambda       |
| `HCP_TERRAFORM_ORG`            | HCP Terraform organization      |
| `HCP_TERRAFORM_PROJECT`        | HCP Terraform project           |
| `HCP_TERRAFORM_WORKSPACE_DEV`  | Dev Terraform workspace         |
| `HCP_TERRAFORM_WORKSPACE_PROD` | Prod Terraform workspace        |
| `DISCORD_PUBLIC_KEY_DEV`       | Discord bot public key (dev)    |
| `DISCORD_PUBLIC_KEY_PROD`      | Discord bot public key (prod)   |

**Secrets** (stored in GitHub Actions secrets, not in config.env):

- `DISCORD_BOT_TOKEN_DEV` / `DISCORD_BOT_TOKEN_PROD`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `TF_TOKEN` (HCP Terraform API token)
- `STARTGG_API_TOKEN` (stored in AWS Secrets Manager at runtime)
- `STARTGG_OAUTH_CLIENT_ID_DEV` / `STARTGG_OAUTH_CLIENT_ID_PROD` (start.gg OAuth app client ID)
- `STARTGG_OAUTH_CLIENT_SECRET_DEV` / `STARTGG_OAUTH_CLIENT_SECRET_PROD` (start.gg OAuth app client secret)

**Main Lambda environment variables** (injected by Terraform):

- `REGION`
- `PUBLIC_KEY`
- `DISCORD_BOT_TOKEN`
- `DYNAMODB_TABLE_NAME`
- `REMOVE_ROLE_QUEUE_URL`
- `STARTGG_SECRET_NAME`
- `STARTGG_OAUTH_CLIENT_ID`
- `STARTGG_OAUTH_REDIRECT_URI`

**OAuth callback Lambda environment variables** (injected by Terraform):

- `REGION`
- `DYNAMODB_TABLE_NAME`
- `STARTGG_OAUTH_SECRET_NAME`
- `OAUTH_REDIRECT_URI`
- `DISCORD_BOT_TOKEN`

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
4. **register-commands** _(manual trigger only)_ — register slash commands with Discord

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
