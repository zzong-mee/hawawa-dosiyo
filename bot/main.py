"""Hawawa Dosiyo entry point. Extensions will be added as they are migrated."""
import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv


class HawawaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        await self.load_extension("bot.cogs.general")
        await self.tree.sync()


async def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "replace_with_new_bot_token":
        raise RuntimeError("Set a new DISCORD_TOKEN in the environment")
    async with HawawaBot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
