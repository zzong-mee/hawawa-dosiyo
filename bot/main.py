"""Clean-room Hawawa Dosiyo bot: start small, add features only after tests."""
import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.errors import HawawaTree

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("hawawa")

class HawawaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = os.getenv("ENABLE_MEMBER_EVENTS", "false").strip().lower() == "true"
        intents.message_content = os.getenv("ENABLE_MESSAGE_CONTENT", "false").strip().lower() == "true"
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, tree_cls=HawawaTree)

    async def setup_hook(self):
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.utility")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.cogs.information")
        await self.load_extension("bot.cogs.community")
        await self.load_extension("bot.cogs.reminders")
        await self.load_extension("bot.cogs.role_panels")
        await self.load_extension("bot.cogs.server_events")
        await self.load_extension("bot.cogs.automod")
        await self.load_extension("bot.cogs.temporary_roles")
        await self.load_extension("bot.cogs.giveaways")
        await self.load_extension("bot.cogs.starboard")
        await self.load_extension("bot.cogs.moderation_records")
        await self.load_extension("bot.cogs.automation")
        await self.load_extension("bot.cogs.role_automation")
        await self.load_extension("bot.cogs.extras")
        await self.load_extension("bot.cogs.announcements")
        await self.load_extension("bot.cogs.suggestions")
        await self.load_extension("bot.cogs.level_rewards")

        guild_id = os.getenv("TEST_GUILD_ID", "").strip()
        scope = os.getenv("COMMAND_SYNC_SCOPE", "auto").strip().lower()
        if scope not in {"auto", "test", "global", "off"}:
            raise RuntimeError("COMMAND_SYNC_SCOPE must be auto, test, global, or off")
        if scope == "off":
            logger.info("Command synchronization disabled")
            return
        if scope == "test" and not guild_id:
            raise RuntimeError("TEST_GUILD_ID is required for test command synchronization")
        if scope == "global":
            guild_id = ""
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced test guild commands: %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced global commands")

    async def on_ready(self):
        logger.info("Logged in as %s (id=%s)", self.user, self.user.id)

async def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "replace_with_new_bot_token":
        raise RuntimeError("Set DISCORD_TOKEN in your local .env file")
    async with HawawaBot() as bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
