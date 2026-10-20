"""Safe, exact-match text triggers and reusable announcement embeds."""

import logging
import re
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed

from bot.storage import Store

logger = logging.getLogger("hawawa.automation")


def render_template(text, user, guild):
    # Only replace fixed placeholders. No expressions, attributes, or evaluation.
    values = {"user": discord.utils.escape_markdown(user.display_name), "server": discord.utils.escape_markdown(guild.name)}
    return re.sub(r"\{(user|server)\}", lambda match: values[match.group(1)], text)[:1800]


class Automation(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.cooldowns = {}

    @app_commands.command(name="trigger", description="정확히 일치하는 채팅에 자동 응답을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(action="set: 저장, list: 목록, remove: 삭제", keyword="정확히 일치할 채팅", response="응답 ({user}, {server} 치환 가능)")
    async def trigger(
        self, interaction: discord.Interaction, action: Literal["set", "list", "remove"],
        keyword: app_commands.Range[str, 1, 100] | None = None,
        response: app_commands.Range[str, 1, 1500] | None = None,
    ):
        if action != "list" and (not keyword or not keyword.strip()):
            await interaction.response.send_message("keyword를 입력해주세요.", ephemeral=True)
            return
        if action == "set" and (not response or not response.strip()):
            await interaction.response.send_message("response를 입력해주세요.", ephemeral=True)
            return
        if action == "set" and not self.bot.intents.message_content:
            await interaction.response.send_message("Developer Portal의 Message Content Intent와 ENABLE_MESSAGE_CONTENT=true를 먼저 활성화해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = keyword.strip().casefold() if keyword else None
        if action == "set":
            # Server cap prevents unbounded automatic reply configurations.
            rows = await self.store.execute("INSERT INTO triggers SELECT ?,?,? WHERE (SELECT COUNT(*) FROM triggers WHERE guild=?)<100 OR EXISTS(SELECT 1 FROM triggers WHERE guild=? AND keyword=?) ON CONFLICT(guild,keyword) DO UPDATE SET response=excluded.response RETURNING keyword", (interaction.guild.id, key, response.strip(), interaction.guild.id, interaction.guild.id, key))
            text = "자동 응답을 저장했습니다." if rows else "서버당 자동 응답은 최대 100개입니다."
        elif action == "remove":
            rows = await self.store.execute("DELETE FROM triggers WHERE guild=? AND keyword=? RETURNING keyword", (interaction.guild.id, key))
            text = "자동 응답을 삭제했습니다." if rows else "등록된 자동 응답이 없습니다."
        else:
            rows = await self.store.execute("SELECT keyword FROM triggers WHERE guild=? ORDER BY keyword LIMIT 15", (interaction.guild.id,))
            text = "\n".join(discord.utils.escape_markdown(row[0]) for row in rows) or "자동 응답이 없습니다."
            text += "\n목록은 최대 15개까지 표시합니다."
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.bot.intents.message_content or message.guild is None or message.author.bot or message.webhook_id or not message.content:
            return
        key = (message.guild.id, message.channel.id)
        now = time.monotonic()
        if now - self.cooldowns.get(key, -100) < 10:
            return
        try:
            rows = await self.store.execute("SELECT response FROM triggers WHERE guild=? AND keyword=?", (message.guild.id, message.content.strip().casefold()))
            if not rows:
                return
            if now - self.cooldowns.get(key, -100) < 10:
                return
            self.cooldowns[key] = now
            if len(self.cooldowns) > 5000:
                self.cooldowns = {key: value for key, value in self.cooldowns.items() if now - value < 10}
            await message.channel.send(render_template(rows[0][0], message.author, message.guild), allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("Automatic response failed in guild %s", message.guild.id)

    @app_commands.command(name="embed", description="현재 채널에 안내 임베드를 게시합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(title="안내 제목", text="본문 ({user}, {server} 치환 가능)")
    async def embed(self, interaction: discord.Interaction, title: app_commands.Range[str, 1, 200], text: app_commands.Range[str, 1, 1500]):
        permissions = interaction.app_permissions
        if not (interaction.permissions.send_messages and permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message("실행자·봇의 메시지 전송 권한과 봇의 임베드 권한이 필요합니다.", ephemeral=True)
            return
        if not title.strip() or not text.strip():
            await interaction.response.send_message("제목과 본문을 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed = make_embed(title=f"📣 {title.strip()}", description=render_template(text, interaction.user, interaction.guild), kind="warning")
        await interaction.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.followup.send("안내 메시지를 게시했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Automation(bot))
