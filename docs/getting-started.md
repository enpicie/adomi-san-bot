---
layout: default
title: Getting Started
---

# Getting Started

Adomi-san is self-hosted — you deploy your own instance on AWS and connect it to your Discord server.

---

## Prerequisites

- An AWS account
- A Discord application and bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- A start.gg account (for start.gg features)
- Terraform + HCP Terraform Cloud (for infrastructure)

---

## 1. Deploy the Bot

Clone the repository and follow the infrastructure setup in the [GitHub repo](https://github.com/enpicie/adomi-san-bot).

The bot runs on AWS Lambda + API Gateway. Deployment is handled via GitHub Actions and Terraform.

---

## 2. Add the Bot to Your Server

Invite the bot to your Discord server using the OAuth2 URL from your Discord application page.
Make sure it has the following permissions:

- Manage Roles
- Read Messages / Send Messages
- Use Slash Commands

---

## 3. Initialize Your Server

Once the bot is in your server, run:

```
/setup-server organizer_role: @YourOrganizerRole
```

This initializes the bot's config for your server. The role you provide will gate all organizer commands.

---

## 4. Optional Setup

| Command | What it does |
|---|---|
| `/set-default-participant-role` | Set the default role assigned to participants on check-in |
| `/startgg-connect` | Link a start.gg organizer account for score reporting |
| `/league-create` | Set up a Google Sheets-backed league |

---

## Participant Role Resolution

When a participant checks in, the bot assigns a role in this order:

1. Event-specific role (set at event creation or update)
2. Server default (`/set-default-participant-role`)
3. None (a warning is shown)

---

## Need Help?

See the [Commands](commands) page for a full reference, or message **@enpicie** on Discord.
