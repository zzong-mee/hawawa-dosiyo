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

Try `/핑` in Discord. To sync the slash command immediately to a test server, set `TEST_GUILD_ID` in your local `.env` (server ID, not token).

**Security:** Never commit `.env`, tokens, or original SQLite databases. Never copy unaudited legacy Git history into this public repository.

## Plan

Add functionality one module at a time with tests: core, moderation, music, economy, attendance, and server settings. Design an explicit, backed-up data migration only after the new schema is stable.
