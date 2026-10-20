"""Grant ordinary roles for a limited time and revoke them after restarts."""

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.cogs.community import safe_role
from bot.storage import Store

logger = logging.getLogger("hawawa.temporary_roles")


class TemporaryRoles(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.expire.is_running():
            self.expire.start()

    def cog_unload(self):
        self.expire.cancel()

    @app_commands.command(name="temprole", description="일반 역할을 일정 시간 지급한 뒤 자동 회수합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(member="역할을 받을 멤버", role="지급할 일반 역할", minutes="지급 기간 (1분~30일)")
    async def temprole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, minutes: app_commands.Range[int, 1, 43200]):
        guild = interaction.guild
        if member.guild.id != guild.id or member.id == guild.owner_id or not safe_role(guild, role) or (
            interaction.user.id != guild.owner_id and (role >= interaction.user.top_role or member.top_role >= interaction.user.top_role)
        ) or member.top_role >= guild.me.top_role:
            await interaction.response.send_message("역할·대상 멤버가 실행자와 봇보다 낮아야 하며, 관리 권한이 없는 일반 역할만 지급할 수 있습니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.lock:
            current = await guild.fetch_member(member.id)
            rows = await self.store.execute("SELECT due FROM temporary_roles WHERE guild=? AND user=? AND role=?", (guild.id, member.id, role.id))
            if role in current.roles and not rows:
                await interaction.followup.send("이미 보유한 일반 역할에는 자동 회수를 예약하지 않습니다.", ephemeral=True)
                return
            due = time.time() + minutes * 60
            # Save before the API call so a crash cannot leave an untracked grant.
            await self.store.execute("INSERT INTO temporary_roles VALUES (?,?,?,?) ON CONFLICT(guild,user,role) DO UPDATE SET due=excluded.due", (guild.id, member.id, role.id, due))
            await current.add_roles(role, reason=f"Temporary role by {interaction.user.id}")
        await interaction.followup.send(f"기간 역할을 지급했습니다. <t:{int(due)}:R> 회수합니다.", ephemeral=True)

    async def expire_once(self, now=None):
        now = time.time() if now is None else now
        async with self.lock:
            rows = await self.store.execute("SELECT guild,user,role FROM temporary_roles WHERE due<=? LIMIT 50", (now,))
            for guild_id, user_id, role_id in rows:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue
                role = guild.get_role(role_id)
                try:
                    if role:
                        member = await guild.fetch_member(user_id)
                        if role in member.roles:
                            await member.remove_roles(role, reason="Temporary role expired")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    logger.warning("Temporary role removal failed in guild %s", guild_id)
                    await self.store.execute("UPDATE temporary_roles SET due=? WHERE guild=? AND user=? AND role=?", (now + 60, guild_id, user_id, role_id))
                    continue
                await self.store.execute("DELETE FROM temporary_roles WHERE guild=? AND user=? AND role=?", (guild_id, user_id, role_id))

    @tasks.loop(seconds=15)
    async def expire(self):
        try:
            await self.expire_once()
        except Exception:
            logger.exception("Temporary role expiry failed")

    async def cog_app_command_error(self, interaction, error):
        logger.error("Temporary role command failed: %s", type(error).__name__)
        text = "기간 역할 처리에 실패했습니다. 역할 관리 권한·역할 순서를 확인해주세요."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TemporaryRoles(bot))
