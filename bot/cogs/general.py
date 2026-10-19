"""General slash commands."""

import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="봇 연결 상태를 확인합니다.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"퐁! {round(self.bot.latency * 1000)}ms", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
