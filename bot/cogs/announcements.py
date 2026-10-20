"""Sticky notices and fixed-placeholder greeting templates."""

import asyncio
import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.automation import render_template
from bot.storage import Store

logger = logging.getLogger("hawawa.announcements")


class Announcements(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()

    @app_commands.command(name="greetingtemplate", description="환영·퇴장 안내 문구를 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(kind="안내 종류", text="문구 ({user}, {server} 치환 가능, 생략하면 조회)")
    async def greetingtemplate(self, interaction: discord.Interaction, kind: Literal["welcome", "goodbye"], text: app_commands.Range[str, 1, 1500] | None = None):
        if text is not None and not text.strip():
            await interaction.response.send_message("문구를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if text:
            await self.store.set(interaction.guild.id, kind + "_template", text.strip())
        current = await self.store.get(interaction.guild.id, kind + "_template")
        await interaction.followup.send(current or "기본 문구를 사용합니다.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="sticky", description="현재 채널의 하단 안내 메시지를 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(text="안내 문구 (생략하면 조회)", disable="갱신 중지 (기존 메시지 유지)")
    async def sticky(self, interaction: discord.Interaction, text: app_commands.Range[str, 1, 1500] | None = None, disable: bool = False):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("서버 텍스트 채널에서 사용해주세요.", ephemeral=True)
            return
        if text and disable or text is not None and not text.strip():
            await interaction.response.send_message("문구를 입력하거나 disable만 선택해주세요.", ephemeral=True)
            return
        if text and not (interaction.app_permissions.send_messages and interaction.app_permissions.read_message_history):
            await interaction.response.send_message("봇의 메시지 전송·기록 보기 권한이 필요합니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = (interaction.guild.id, interaction.channel.id)
        async with self.lock:
            if disable:
                await self.store.execute("DELETE FROM sticky_messages WHERE guild=? AND channel=?", key)
                result = "하단 안내 갱신을 중지했습니다. 기존 메시지는 유지합니다."
            elif text:
                await self.store.execute("INSERT INTO sticky_messages (guild,channel,text) VALUES (?,?,?) ON CONFLICT(guild,channel) DO UPDATE SET text=excluded.text,last=0", key + (text.strip(),))
                result = "안내를 설정했습니다. 다음 일반 메시지부터 하단에 갱신합니다."
            else:
                rows = await self.store.execute("SELECT text FROM sticky_messages WHERE guild=? AND channel=?", key)
                result = rows[0][0] if rows else "설정된 하단 안내가 없습니다."
        await interaction.followup.send(result, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot or message.webhook_id or not isinstance(message.channel, discord.TextChannel):
            return
        try:
            async with self.lock:
                key = (message.guild.id, message.channel.id)
                rows = await self.store.execute("SELECT text,post,last FROM sticky_messages WHERE guild=? AND channel=?", key)
                now = time.time()
                if not rows or now - rows[0][2] < 30:
                    return
                text, old, _ = rows[0]
                post = await message.channel.send(render_template(text, message.author, message.guild), allowed_mentions=discord.AllowedMentions.none())
                await self.store.execute("UPDATE sticky_messages SET post=?,last=? WHERE guild=? AND channel=?", (post.id, now) + key)
                if old:
                    try:
                        await message.channel.get_partial_message(old).delete()
                    except discord.HTTPException:
                        logger.warning("Old sticky notice could not be removed in guild %s", message.guild.id)
        except Exception:
            logger.exception("Sticky update failed")


async def setup(bot: commands.Bot):
    await bot.add_cog(Announcements(bot))
