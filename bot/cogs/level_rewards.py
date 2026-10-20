"""Ordinary-role rewards for the built-in experience system."""

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.community import safe_role
from bot.storage import Store
from bot.presentation import role_name


class LevelRewards(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()

    @app_commands.command(name="levelreward", description="레벨 도달 시 지급할 일반 역할을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(action="set: 설정, remove: 설정 삭제, list: 목록", level="필요 레벨", role="지급할 일반 역할")
    async def levelreward(self, interaction: discord.Interaction, action: Literal["set", "remove", "list"], level: app_commands.Range[int, 1, 10000] = 1, role: discord.Role | None = None):
        if action == 'set' and (role is None or not safe_role(interaction.guild, role) or (
            interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role
        )):
            await interaction.response.send_message("실행자와 봇보다 낮으며 관리 권한이 없는 일반 역할을 선택해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild.id
        if action == 'set':
            await self.store.execute("INSERT INTO level_roles VALUES (?,?,?) ON CONFLICT(guild,level) DO UPDATE SET role=excluded.role", (guild, level, role.id))
            text = "레벨 보상을 설정했습니다. 다음 경험치 지급 시 적용합니다."
        elif action == 'remove':
            await self.store.execute("DELETE FROM level_roles WHERE guild=? AND level=?", (guild, level))
            text = "설정을 삭제했습니다. 기존에 지급한 역할은 유지됩니다."
        else:
            rows = await self.store.execute("SELECT level,role FROM level_roles WHERE guild=? ORDER BY level LIMIT 25", (guild,))
            text = "\n".join(f"레벨 {level} · {role_name(interaction.guild, role)}" for level, role in rows) or "설정된 보상이 없습니다."
        await interaction.followup.send(text, ephemeral=True)

    async def award(self, member, xp):
        if not isinstance(member, discord.Member):
            return
        rows = await self.store.execute("SELECT role FROM level_roles WHERE guild=? AND level<=?", (member.guild.id, xp // 100))
        for role_id, in rows:
            role = member.guild.get_role(role_id)
            if role and role not in member.roles and safe_role(member.guild, role):
                await member.add_roles(role, reason="Experience level reward")


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelRewards(bot))
