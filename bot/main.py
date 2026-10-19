"""Hawawa Dosiyo Discord bot."""
import asyncio
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

EXTENSIONS = [
    "settings", "stock", "dailycheck", "clear", "emoji",
    "help", "logs", "music", "sticker", "general",
]

class HawawaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        db_path = Path(os.getenv("DATABASE_PATH", "data/hawawa.db"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        for extension in EXTENSIONS:
            await self.load_extension(f"bot.cogs.{extension}")
        await self.tree.sync()

async def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "replace_with_new_bot_token":
        raise RuntimeError("Set a newly issued DISCORD_TOKEN")
    async with HawawaBot() as bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
