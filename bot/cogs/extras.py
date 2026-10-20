"""Small games and complete-cache member inspection."""

import random
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands


class Extras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="동전을 던집니다.")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(["🪙 앞면", "🪙 뒷면"]), ephemeral=True)

    @app_commands.command(name="rps", description="봇과 가위바위보를 합니다.")
    @app_commands.describe(choice="내가 낼 손")
    async def rps(self, interaction: discord.Interaction, choice: Literal["가위", "바위", "보"]):
        opponent = random.choice(["가위", "바위", "보"])
        result = "무승부" if choice == opponent else "승리" if (choice, opponent) in {("가위", "보"), ("바위", "가위"), ("보", "바위")} else "패배"
        await interaction.response.send_message(f"나: {choice} · 봇: {opponent}\n{result}", ephemeral=True)

    @app_commands.command(name="members", description="계정 생성일 또는 가입일로 멤버를 정렬합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(order="정렬 기준", count="표시할 인원")
    async def members(self, interaction: discord.Interaction, order: Literal["oldest", "youngest", "newjoins", "oldjoins"] = "newjoins", count: app_commands.Range[int, 1, 25] = 10):
        guild = interaction.guild
        if not self.bot.intents.members or not guild.chunked:
            await interaction.response.send_message("완전한 멤버 목록이 필요합니다. Members Intent를 활성화하고 봇의 초기 로딩이 끝난 후 사용해주세요.", ephemeral=True)
            return
        joined = order in ("newjoins", "oldjoins")
        members = [member for member in guild.members if not joined or member.joined_at is not None]
        selected = sorted(members, key=lambda member: member.joined_at if joined else member.created_at, reverse=order in ("youngest", "newjoins"))[:count]
        lines = [f"{index}. {member.id} · <t:{int((member.joined_at if joined else member.created_at).timestamp())}:f>" for index, member in enumerate(selected, 1)]
        await interaction.response.send_message("\n".join(lines) or "해당 멤버가 없습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Extras(bot))
