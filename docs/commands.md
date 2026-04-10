---
layout: default
title: Commands
---

# Commands

> **Organizer role** is configured per-server using `/setup-server`. Most management commands require it.

---

<details>
<summary>Event Commands</summary>

All require the **organizer role**.

| Command | Description |
|---|---|
| `/event-create` | Create a new event manually |
| `/event-update` | Update an existing event's details |
| `/event-delete` | Delete an event |
| `/event-create-startgg` | Import an event from a start.gg tournament link |
| `/event-update-startgg` | Link an existing event to start.gg and import participants |
| `/event-refresh-startgg` | Re-sync participants from start.gg |
| `/event-list` | List all active events on the server |

</details>

---

<details>
<summary>Registration Commands</summary>

| Command | Who can use | Description |
|---|---|---|
| `/register` | Any user (organizer can register others) | Register for an event |
| `/register-list` | Organizer | List all registered participants |
| `/register-remove` | Organizer | Remove a user from registration |
| `/register-clear` | Organizer | Clear the entire registration list |
| `/register-toggle` | Organizer | Open or close registration for an event |

</details>

---

<details>
<summary>Check-In Commands</summary>

Checking in assigns the event's participant role to the user.

| Command | Who can use | Description |
|---|---|---|
| `/check-in` | Any registered user | Check in and receive participant role |
| `/check-in-list` | Organizer | List all checked-in participants |
| `/check-in-clear` | Organizer | Clear check-ins and remove participant roles |
| `/check-in-list-absent` | Organizer | List registered users who have not checked in |
| `/check-in-toggle` | Organizer | Open or close check-ins for an event |

</details>

---

<details>
<summary>Setup Commands</summary>

Require the **Manage Server** Discord permission.

| Command | Description |
|---|---|
| `/setup-server` | Initialize server config with an organizer role |
| `/set-organizer-role` | Update the organizer role |
| `/set-default-participant-role` | Set the default role assigned on check-in |
| `/show-event-roles` | Display the participant role configured for a specific event |

</details>

---

<details>
<summary>Score Reporting (start.gg)</summary>

An organizer must run `/startgg-connect` first to link their start.gg account.
Participants must have their Discord account linked in their start.gg profile under **Edit Profile → Connections**.

| Command | Who can use | Description |
|---|---|---|
| `/startgg-connect` | Organizer | Link a start.gg account to this server via OAuth |
| `/startgg-report-score` | Any participant | Report the result of a bracket set |
| `/startgg-notify-unlinked` | Organizer | List participants who haven't linked their Discord on start.gg |

</details>

---

<details>
<summary>League Commands</summary>

Manages long-running leagues via Google Sheets. The league's sheet must be shared with **Editor** access
to the bot's service account email — run `/league-view` to see that address.

| Command | Who can use | Description |
|---|---|---|
| `/league-create` | Organizer | Create a new league record |
| `/league-update` | Organizer | Update league name, sheet link, or role |
| `/league-list` | Organizer | List all leagues for this server |
| `/league-view` | Organizer | View details of a specific league |
| `/league-setup` | Organizer | Initialize the Participants sheet |
| `/league-delete` | Organizer | Delete a league record |
| `/league-join-toggle` | Organizer | Open or close joining |
| `/league-report-toggle` | Organizer | Open or close score reporting |
| `/league-sync-participants` | Organizer | Sync active participants and assign/remove Discord roles |
| `/league-join` | Any user | Join a league |
| `/league-report-score` | Any user | Report a league match result |
| `/league-deactivate` | Any user (organizer to target others) | Mark a player as inactive or DNF |

</details>

---

<details>
<summary>Help Commands</summary>

| Command | Description |
|---|---|
| `/help` | General help overview |
| `/help-event` | Help for event commands |
| `/help-register` | Help for registration commands |
| `/help-check-in` | Help for check-in commands |
| `/help-startgg` | Help for start.gg score reporting commands |
| `/help-league` | Help for league management commands |

</details>
