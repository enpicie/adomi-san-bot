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
