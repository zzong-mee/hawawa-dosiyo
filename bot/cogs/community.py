"""Persistent server settings, greetings, auto roles, and saved replies."""

import logging
import re
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.storage import Store
from bot.presentation import channel_name, role_name
from bot.cogs.automation import render_template

logger = logging.getLogger("hawawa.community")


def safe_role(guild: discord.Guild, role: discord.Role) -> bool:
    privileged = any(
        enabled and (name.startswith("manage_") or name in {
            "administrator", "moderate_members", "kick_members", "ban_members",
            "mention_everyone", "mute_members", "deafen_members", "move_members",
        })
        for name, enabled in role.permissions
    )
    return (
        role.guild.id == guild.id and not role.is_default() and not role.managed
        and not privileged
        and guild.me is not None and guild.me.guild_permissions.manage_roles
        and role < guild.me.top_role
    )


class Community(commands.Cog):
    def __init__(self, bot: commands.Bot, store: Store | None = None):
        self.bot = bot
        self.store = store or Store()

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.CommandInvokeError):
            logger.error("Community command failed: %s", type(error.original).__name__)
            text = "처리에 실패했습니다. 잠시 후 다시 시도해주세요."
        else:
            text = "서버에서 필요한 관리 권한을 가진 사용자만 실행할 수 있습니다."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="tag", description="서버에 저장된 응답을 조회하거나 관리합니다.")
    @app_commands.guild_only()
    @app_commands.describe(action="show: 조회, list: 목록, set: 저장/수정, remove: 삭제", name="태그 이름 (영문·숫자·한글·밑줄·하이픈)", content="저장할 응답")
    async def tag(
        self, interaction: discord.Interaction,
        action: Literal["show", "list", "set", "remove"],
        name: app_commands.Range[str, 1, 32] | None = None,
        content: app_commands.Range[str, 1, 1800] | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
        if action in ("set", "remove") and not interaction.permissions.manage_guild:
            await interaction.response.send_message("태그 수정에는 서버 관리 권한이 필요합니다.", ephemeral=True)
            return
        key = name.strip().lower() if name else None
        if action != "list" and (not key or not re.fullmatch(r"[\w-]{1,32}", key)):
            await interaction.response.send_message("유효한 태그 이름을 입력해주세요.", ephemeral=True)
            return
        if action == "set" and (not content or not content.strip()):
            await interaction.response.send_message("저장할 응답을 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild_id = interaction.guild.id
        if action == "list":
            rows = await self.store.execute("SELECT name FROM tags WHERE guild=? ORDER BY name LIMIT 51", (guild_id,))
            text = ", ".join(row[0] for row in rows[:50]) or "저장된 태그가 없습니다."
            if len(rows) > 50:
                text += "\n앞의 50개만 표시합니다."
        elif action == "set":
            await self.store.execute("INSERT INTO tags VALUES (?, ?, ?) ON CONFLICT(guild,name) DO UPDATE SET content=excluded.content", (guild_id, key, content.strip()))
            text = "태그를 저장했습니다."
        elif action == "remove":
            rows = await self.store.execute("DELETE FROM tags WHERE guild=? AND name=? RETURNING name", (guild_id, key))
            text = "태그를 삭제했습니다." if rows else "해당 태그가 없습니다."
        else:
            rows = await self.store.execute("SELECT content FROM tags WHERE guild=? AND name=?", (guild_id, key))
            text = rows[0][0] if rows else "해당 태그가 없습니다."
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="welcome", description="입장 안내 채널을 설정하거나 해제합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="안내 채널 (생략하면 설정 조회)", disable="입장 안내 해제")
    async def welcome(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None, disable: bool = False):
        if disable and channel is not None:
            await interaction.response.send_message("채널 설정과 해제를 동시에 사용할 수 없습니다.", ephemeral=True)
            return
        if channel and not self.bot.intents.members:
            await interaction.response.send_message("ENABLE_MEMBER_EVENTS=true 설정과 Developer Portal의 Server Members Intent 활성화가 필요합니다.", ephemeral=True)
            return
        if channel:
            permissions = channel.permissions_for(interaction.guild.me)
            if channel.guild.id != interaction.guild.id or not (permissions.view_channel and permissions.send_messages):
                await interaction.response.send_message("봇이 메시지를 보낼 수 있는 이 서버의 채널을 선택해주세요.", ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if channel or disable:
            await self.store.set(interaction.guild.id, "welcome", str(channel.id) if channel else "")
        value = await self.store.get(interaction.guild.id, "welcome")
        await interaction.followup.send(f"입장 안내: {channel_name(interaction.guild, value)}" if value else "입장 안내가 꺼져 있습니다.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="autorole", description="신규 멤버 자동 역할을 설정하거나 해제합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(role="자동 지급 역할 (생략하면 조회)", disable="자동 역할 해제")
    async def autorole(self, interaction: discord.Interaction, role: discord.Role | None = None, disable: bool = False):
        if role and disable:
            await interaction.response.send_message("역할 설정과 해제를 동시에 사용할 수 없습니다.", ephemeral=True)
            return
        if role:
            if not self.bot.intents.members:
                await interaction.response.send_message("ENABLE_MEMBER_EVENTS=true 설정과 Server Members Intent 활성화가 필요합니다.", ephemeral=True)
                return
            if not safe_role(interaction.guild, role) or (
                interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role
            ):
                await interaction.response.send_message("관리 권한이 없는 일반 역할이며 실행자와 봇보다 낮은 역할을 선택해주세요.", ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if role or disable:
            await self.store.set(interaction.guild.id, "autorole", str(role.id) if role else "")
        value = await self.store.get(interaction.guild.id, "autorole")
        await interaction.followup.send(f"자동 역할: {role_name(interaction.guild, value)}" if value else "자동 역할이 꺼져 있습니다.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        try:
            value = await self.store.get(member.guild.id, "autorole")
            role = member.guild.get_role(int(value)) if value else None
            if role and safe_role(member.guild, role):
                try:
                    await member.add_roles(role, reason="Configured join auto role")
                except discord.HTTPException:
                    logger.warning("Auto role failed in guild %s", member.guild.id)
            value = await self.store.get(member.guild.id, "welcome")
            channel = member.guild.get_channel(int(value)) if value else None
            if isinstance(channel, discord.TextChannel):
                template = await self.store.get(member.guild.id, "welcome_template") or "{user}님, 환영합니다!"
                await channel.send(render_template(template, member, member.guild), allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("Member join processing failed in guild %s", member.guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))
