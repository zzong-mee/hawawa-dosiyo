"""Dosiyo utility commands migrated to slash commands."""
import random
from urllib.parse import quote_plus

import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    @app_commands.command(name="주사위", description="1부터 6까지 주사위를 굴립니다.")
    async def dice(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎲 {random.randint(1, 6)}")

    @app_commands.command(name="검색", description="구글과 유튜브 검색 링크를 표시합니다.")
    @app_commands.describe(검색어="검색할 단어")
    async def search(self, interaction: discord.Interaction, 검색어: str):
        q = quote_plus(검색어)
        await interaction.response.send_message(
            f"구글: https://www.google.com/search?q={q}\n"
            f"유튜브: https://www.youtube.com/results?search_query={q}",
            ephemeral=True,
        )

    @app_commands.command(name="프로필", description="사용자의 디스코드 프로필을 확인합니다.")
    async def profile(self, interaction: discord.Interaction, 사용자: discord.Member | None = None):
        target = 사용자 or interaction.user
        embed = discord.Embed(title="사용자 프로필", color=0xFFCFCF)
        embed.add_field(name="이름", value=target.display_name)
        embed.add_field(name="ID", value=str(target.id))
        embed.add_field(name="가입일", value=discord.utils.format_dt(target.created_at, "D"))
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="서버정보", description="현재 서버의 정보를 확인합니다.")
    @app_commands.guild_only()
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        embed = discord.Embed(title=guild.name, color=0xFFCFCF)
        embed.add_field(name="서버장", value=guild.owner.mention if guild.owner else "알 수 없음")
        embed.add_field(name="멤버 수", value=str(guild.member_count or 0))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(General())
