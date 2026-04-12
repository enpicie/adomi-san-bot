---
layout: default
title: Adomin
---

# Adomin! ☆

**Adomi-san** (or **Adomin** for short) is here to help as a Discord event administration assistant. She helps make you manage events organically within Discord, automating work to make events visible, notify event participants, and more! With special training to support FGC tournaments hosted on [start.gg](https://start.gg), she simplifies score reporting while letting you count player check-ins without extra steps in start.gg itself.

Here are some Quick Start guides to get started with events via Adomin! Use the `/help` and `/help-*` commands to get help in Discord.

## Guide
- [First-Time Server Setup](#first-time-server-setup)
- [Running a start.gg Tournament](#running-a-startgg-tournament)
- [Running an Event (Exhibition, etc.)](#running-an-event-eg-exhibition-other-non-tournament-event)
- [Running a League](#running-a-league)

## First-Time Server Setup

These steps only need to be done once per server.

1. Create a Discord role for event organizers. Users with this role can run privileged commands. Organizers should be anyone you want to be allowed to manage events in your server.
2. Run `/setup-server` and provide that role as `organizer_role`.
3. *(Optional)* Run `/set-default-participant-role` to set a role that gets assigned to users when they check in. This can be used to ping active participants mid-event.
4. *(Optional)* Run `/setup-notifications` to configure a channel for notifications such as automated event cleanup or startgg connection notifications.
5. *(Optional)* Run `/setup-event-reminders` to setup automatic reminders for events. These can be configured per-event too, but this command sets up the defaults for your server.

## Running a start.gg Tournament

### Creating the Event

Run `/event-create-startgg` with your bracket link, `end_time`, and `timezone`. Adomi-san will create the event and automatically load all registered entrants into the registration list.

> Example link: `https://www.start.gg/tournament/midweek-melting-1/event/mbaacc-double-elim`

If new entrants sign up after creation, use `/event-refresh-startgg` to re-sync. Data for the event will be cleaned up and the participant role will be removed from all users after the given end time passes.

### On Event Day

1. Open check-in with `/check-in-toggle` (state: **Start**).
2. Participants run `/check-in` — this marks them as present and assigns the participant role if one is configured.
  - Note that this does not check the user in on start.gg itself
3. Use `/check-in-list-absent` (with `ping_users: True`) to ping anyone who hasn't checked in yet.
  - Recommended to run `/event-refresh-startgg` before this if your registration is open and you may have new entrants to sync.
4. When check-in is over, run `/check-in-toggle` (state: **End**).
5. Players can report scores with `/startgg-report-score` (this requires players to have Discord properly linked to start.gg to function correctly).

> Score reporting requires authorization via `/startgg-connect` command where a user with permissions to report scores for the event must authorize Adomin to report scores.

### After the Event

Adomi-san automatically detects when the Discord scheduled event ends and will...
- Remove the participant role from all attendees
- Delete the event data
- Post a notification to your configured notifications channel

You can also manually clean up with `/check-in-clear`, `/register-clear`, and `/event-delete`.

## Running an Event (e.g. Exhibition, other non-tournament event)

### Creating the Event

Run `/event-create` and fill in the required fields: `event_name`, `event_location`, `start_time`, `end_time`, and `timezone`. Optionally add a description and specified Participant Role.

### Before the Event

*Registration is only used to determine who is expected to check-in at event time.* If you have a set of expected participants you want to register, you can run `/register` as an organizer and pass in specific users to register.

To allow users to register themselves:

1. Open registration with `/register-toggle` (state: **Start**) so participants can sign up.
2. Participants run `/register` to add themselves to the list.
3. Organizers can check the list any time with `/register-list`.

### Check-in Management

Check-in affirms participants are present for the event and assigns a Participant role to users as they check in.

1. Open check-in with `/check-in-toggle` (state: **Start**).
2. Participants run `/check-in` — this marks them as present and assigns the participant role if one is configured.
3. Use `/check-in-list-absent` (with `ping_users: True`) to ping anyone who hasn't checked in yet.
4. When check-in is over, run `/check-in-toggle` (state: **End**).

> One of the main benefits of the Participant role is managing channel access. If you want to use a specific role-gated channel to help plan or run your event, you can make it accessible specifically to users with the Participant role. Participants will then be able to access your channel after checking in.

### After the Event

Adomi-san automatically detects when the Discord scheduled event ends and will:
- Remove the participant role from all attendees
- Delete the event data
- Post a notification to your configured notifications channel

You can also manually clean up with `/check-in-clear`, `/register-clear`, and `/event-delete`.

## Running a League

Adomi-san manages leagues in partnership with [fgc-league-sheets](https://github.com/enpicie/fgc-league-sheets), a Google Sheets extension that handles the actual league automation: distributing players into groups, generating score matrices, and calculating tier promotions and demotions at the end of each rotation. The bot handles everything Discord-side — player sign-ups, score reporting, and keeping Discord roles in sync with the sheet.

**Adomi-san talks to the Google Sheet directly.** The fgc-league-sheets extension runs separately within Google Sheets itself, managing rotation cycles. Organizers interact with both.

> Note: League functionality is still actively undergoing testing primarily via DMF Duel League for MBAACC. Contact **@enpicie** for any questions or issues experienced.

### First-Time League Setup

These steps only need to be done once per league.

1. Copy the [FGC League Template](https://docs.google.com/spreadsheets/d/1FojOkjQJD1dtr29fwH8bgabIdfxd-Yp72V0-pqbIqcc/edit?usp=sharing) sheet to get the starter sheet with latest version of the extension.
  - Regardless of the stated version number, this sheet always has the latest version of the Google Sheets extension.
2. Share the sheet with the bot's service account. The account email is shown when you run `/league-create`.
3. Run `/league-create` with the league name, a short unique ID (max 4 characters, e.g. `MBAA`), the Google Sheets link, and optionally an `active_participant_role` to assign to active league members.
4. Run `/league-setup` to initialize the Participants sheet in the linked Google Sheet. This creates the roster the bot and the extension both read from.

### Each Rotation

#### Signing Up

1. Open joining with `/league-join-toggle` (state: **Start**).
2. Players run `/league-join` — this adds them to the Participants sheet with a **QUEUED** status, ready to be picked up when the next rotation starts.
3. Close joining with `/league-join-toggle` (state: **End**).

#### Starting the Rotation (in Google Sheets)

4. Open the Google Sheet and run the **Start Cycle** from the fgc-league-sheets extension. This promotes QUEUED players to ACTIVE, distributes all active players into groups by tier, and generates the score matrix for the rotation.
5. Run `/league-sync-participants` — this reads the sheet and assigns or removes the `active_participant_role` based on who is currently ACTIVE.

#### Reporting Scores

During the rotation, players report their match results in Discord:

- Run `/league-report-score` with the league name, `winner`, `loser`, and `score` (e.g. `3-2`, winner's score first). This writes the result to the score matrix in the Google Sheet.

#### Ending the Rotation (in Google Sheets)

6. Open the Google Sheet and run the **End Cycle** from the fgc-league-sheets extension. This analyzes win percentages, flags promotion and demotion candidates, and marks anyone who didn't complete their matches as inactive. Organizers can review and commit or undo the proposed changes before they take effect.
7. Run `/league-sync-participants` again to update Discord roles to match the new state of the sheet.

### Other League Management

| Task                                    | Command                                                                                  |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| View league details and participant count | `/league-view`                                                                         |
| List all leagues on the server          | `/league-list`                                                                           |
| Mark yourself inactive or DNF          | `/league-deactivate` (optional: `dnf: True`)                                             |
| Deactivate another player (Organizer)  | `/league-deactivate` with `player` set                                                   |
| Update league name, sheet, or role      | `/league-update`                                                                         |
| Delete a league record                  | `/league-delete`                                                                         |