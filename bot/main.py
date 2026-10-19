"""Clean-room Hawawa Dosiyo bot: start small, add features only after tests."""
import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("hawawa")

class HawawaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.utility")
        await self.load_extension("bot.cogs.moderation")

        guild_id = os.getenv("TEST_GUILD_ID", "").strip()
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
