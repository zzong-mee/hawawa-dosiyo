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

    @app_commands.command(name="help", description="사용 가능한 명령어를 확인합니다.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Hawawa Dosiyo 명령어", color=discord.Color.blurple())
        for command in sorted(self.bot.tree.get_commands(), key=lambda command: command.name):
            embed.add_field(
                name=f"/{command.name}", value=command.description, inline=False
            )
        embed.set_footer(text="/serverinfo·/poll·/clear는 서버 전용이며, /clear는 메시지 관리 권한이 필요합니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="현재 서버 정보를 확인합니다.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "서버에서만 사용할 수 있는 명령어입니다.", ephemeral=True
            )
            return

        embed = discord.Embed(title="서버 정보", color=discord.Color.blurple())
        embed.add_field(name="서버 이름", value=guild.name, inline=False)
        member_count = guild.member_count
        embed.add_field(
            name="멤버 수",
            value=f"{member_count:,}명" if member_count is not None else "확인할 수 없음",
        )
        embed.add_field(
            name="생성일", value=discord.utils.format_dt(guild.created_at, style="D")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
