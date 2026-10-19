# Hawawa Dosiyo — v3 rebuild

This branch is a **clean rebuild** of the Discord bot. The previous integrated implementation is preserved in `archive/legacy-unified-2026`. Original Takoyaki and Dosiyo repositories remain untouched.

## Local quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env locally with your NEW Discord bot token
python -m bot.main
```

Try `/ping` in Discord. To sync the slash command immediately to a test server, set `TEST_GUILD_ID` in your local `.env` (server ID, not token).

**Security:** Never commit `.env`, tokens, or original SQLite databases. Never copy unaudited legacy Git history into this public repository.

## Command structure

- `bot/main.py`: starts the bot, loads extensions, and syncs slash commands.
- `bot/cogs/general.py`: defines `/ping`, `/help`, and `/serverinfo`.

All three commands reply only to the user who invoked them. `/help` lists the general commands. `/serverinfo` shows the server name, member count (including bots), and creation date, and is available only in servers.

Add general commands to the `General` Cog. For a new feature, create a module under `bot/cogs/` with an async `setup(bot)` function that registers its Cog, then load it in `HawawaBot.setup_hook()` before syncing commands. Restart the bot to load and sync changes.

### Utilities (no database)

`bot/cogs/utility.py` provides these commands:

| Command | Usage |
| --- | --- |
| `/userinfo` | Account name, ID, creation date and bot status; optional `user` defaults to yourself |
| `/avatar` | Avatar image; optional `user` defaults to yourself |
| `/roll` | Roll 1–20 dice with 2–1000 sides; defaults to one six-sided die |
| `/vote` | Pick from 2–20 unique options separated by `,`, up to 100 characters each |
| `/poll` | Public server poll with 2–10 unique options separated by `,`, up to 55 characters each; 1–168 hours, optional multiple answers |
| `/randomteam` | Split 2–40 unique participants separated by `,` into 2–10 balanced random teams; private response |

Utility responses are private except `/poll`, which publishes a native Discord poll in the channel. The bot needs permission to send messages and create polls. Discord stores the votes, so bot restarts do not erase a published poll. No local database is used.

Run offline tests with `python -B -m unittest discover -s tests -v`.

### Moderation

`bot/cogs/moderation.py` provides `/clear count:1–100` in server text channels and threads. It checks the caller's **Manage Messages** permission in the current channel at execution time. The bot also needs View Channel, Read Message History, and Manage Messages. It examines the requested number of messages sent before the command, preserves pinned messages, and privately reports the actual number deleted. Deletion is permanent; older messages may take longer because Discord requires individual deletion. No database is used.

## Plan

Add functionality one module at a time with tests: core, moderation, music, economy, attendance, and server settings. Design an explicit, backed-up data migration only after the new schema is stable.
