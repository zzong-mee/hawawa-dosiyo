"""Delayed join roles and opt-in restoration of ordinary roles for 30 days."""

import asyncio
import json
import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.cogs.community import safe_role
from bot.storage import Store

logger = logging.getLogger("hawawa.role_automation")


class RoleAutomation(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.assign.is_running():
            self.assign.start()

    def cog_unload(self):
        self.assign.cancel()

    @app_commands.command(name="roleautomation", description="입장 후 지연 역할과 재입장 역할 복원을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(action="delay: 지연 지급, remove: 지연 설정 삭제, list: 목록, restore: 재입장 복원", role="일반 역할", minutes="입장 후 대기 시간", enabled="역할 복원 활성화 여부")
    async def roleautomation(
        self, interaction: discord.Interaction,
        action: Literal["delay", "remove", "list", "restore"],
        role: discord.Role | None = None,
        minutes: app_commands.Range[int, 1, 43200] = 60,
        enabled: bool | None = None,
    ):
        if action in ("delay", "remove") and role is None:
            await interaction.response.send_message("role을 선택해주세요.", ephemeral=True)
            return
        if action == "restore" and not interaction.permissions.manage_guild:
            await interaction.response.send_message("복원 정책에는 서버 관리 권한도 필요합니다.", ephemeral=True)
            return
        if (action == "delay" or action == "restore" and enabled) and not self.bot.intents.members:
            await interaction.response.send_message("Server Members Intent와 ENABLE_MEMBER_EVENTS=true가 필요합니다.", ephemeral=True)
            return
        if action == "delay" and (not safe_role(interaction.guild, role) or (
            interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role
        )):
            await interaction.response.send_message("실행자와 봇보다 낮으며 관리 권한이 없는 일반 역할을 선택해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild.id
        async with self.lock:
            if action == "delay":
                await self.store.execute("INSERT INTO delayed_roles VALUES (?,?,?) ON CONFLICT(guild,role) DO UPDATE SET delay=excluded.delay", (guild, role.id, minutes * 60))
                text = "앞으로 입장하는 일반 멤버의 지연 역할을 설정했습니다."
            elif action == "remove":
                await self.store.execute("DELETE FROM delayed_roles WHERE guild=? AND role=?", (guild, role.id))
                await self.store.execute("DELETE FROM delayed_role_jobs WHERE guild=? AND role=?", (guild, role.id))
                text = "지연 설정과 해당 역할의 대기 작업을 취소했습니다. 기존 역할은 유지합니다."
            elif action == "restore":
                if enabled is not None:
                    await self.store.set(guild, "role_restore", "on" if enabled else "")
                text = "재입장 복원: " + ("켜짐 (30일, 일반 역할만)" if await self.store.get(guild, "role_restore") == "on" else "꺼짐")
            else:
                rows = await self.store.execute("SELECT role,delay FROM delayed_roles WHERE guild=? LIMIT 20", (guild,))
                text = "\n".join(f"역할 ID {identifier} · {delay // 60}분" for identifier, delay in rows) or "지연 역할이 없습니다."
        await interaction.followup.send(text, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        try:
            async with self.lock:
                guild, user = member.guild.id, member.id
                now = time.time()
                rows = await self.store.execute("SELECT role,delay FROM delayed_roles WHERE guild=?", (guild,))
                for role, delay in rows:
                    await self.store.execute("INSERT OR IGNORE INTO delayed_role_jobs VALUES (?,?,?,?)", (guild, user, role, now + delay))
                if await self.store.get(guild, "role_restore") == "on":
                    rows = await self.store.execute("SELECT roles FROM saved_roles WHERE guild=? AND user=? AND expires>?", (guild, user, now))
                    for role in json.loads(rows[0][0]) if rows else []:
                        await self.store.execute("INSERT OR IGNORE INTO delayed_role_jobs VALUES (?,?,?,?)", (guild, user, role, now))
                    await self.store.execute("DELETE FROM saved_roles WHERE guild=? AND user=?", (guild, user))
        except Exception:
            logger.exception("Join role scheduling failed in guild %s", member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot:
            return
        try:
            async with self.lock:
                guild, user = member.guild.id, member.id
                await self.store.execute("DELETE FROM delayed_role_jobs WHERE guild=? AND user=?", (guild, user))
                if await self.store.get(guild, "role_restore") != "on":
                    return
                temporary = {row[0] for row in await self.store.execute("SELECT role FROM temporary_roles WHERE guild=? AND user=?", (guild, user))}
                roles = [role.id for role in member.roles if role.id not in temporary and safe_role(member.guild, role)]
                await self.store.execute("INSERT INTO saved_roles VALUES (?,?,?,?) ON CONFLICT(guild,user) DO UPDATE SET roles=excluded.roles,expires=excluded.expires", (guild, user, json.dumps(roles), time.time() + 30 * 86400))
        except Exception:
            logger.exception("Role snapshot failed in guild %s", member.guild.id)

    async def assign_once(self, now=None):
        now = time.time() if now is None else now
        async with self.lock:
            await self.store.execute("DELETE FROM saved_roles WHERE expires<=?", (now,))
            rows = await self.store.execute("SELECT guild,user,role FROM delayed_role_jobs WHERE due<=? LIMIT 50", (now,))
            for guild_id, user, role_id in rows:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue
                role = guild.get_role(role_id)
                try:
                    if role and safe_role(guild, role):
                        member = await guild.fetch_member(user)
                        await member.add_roles(role, reason="Delayed/restore ordinary role")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    await self.store.execute("UPDATE delayed_role_jobs SET due=? WHERE guild=? AND user=? AND role=?", (now + 60, guild_id, user, role_id))
                    continue
                await self.store.execute("DELETE FROM delayed_role_jobs WHERE guild=? AND user=? AND role=?", (guild_id, user, role_id))

    @tasks.loop(seconds=15)
    async def assign(self):
        try:
            await self.assign_once()
        except Exception:
            logger.exception("Delayed role iteration failed")


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleAutomation(bot))
