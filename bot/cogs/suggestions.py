"""Persistent suggestion voting and moderator decisions."""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

from bot.storage import Store


class SuggestionView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def vote(self, interaction, value):
        if interaction.guild is None or interaction.message is None or interaction.user.bot:
            await interaction.response.send_message("서버의 건의 메시지에서 사용해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = (interaction.guild.id, interaction.message.id)
        async with self.cog.lock:
            rows = await self.cog.store.execute("SELECT author,status FROM suggestions WHERE guild=? AND message=?", key)
            if not rows or rows[0][1] != 'pending':
                await interaction.followup.send("투표가 종료된 건의입니다.", ephemeral=True)
                return
            if value:
                await self.cog.store.execute("INSERT INTO suggestion_votes VALUES (?,?,?,?) ON CONFLICT(guild,message,user) DO UPDATE SET vote=excluded.vote", key + (interaction.user.id, value))
            else:
                await self.cog.store.execute("DELETE FROM suggestion_votes WHERE guild=? AND message=? AND user=?", key + (interaction.user.id,))
            rows = await self.cog.store.execute("SELECT vote,COUNT(*) FROM suggestion_votes WHERE guild=? AND message=? GROUP BY vote", key)
            counts = dict(rows)
            await interaction.message.edit(content=f"👍 **찬성 {counts.get(1, 0)}**　·　👎 **반대 {counts.get(-1, 0)}**", allowed_mentions=discord.AllowedMentions.none())
        await interaction.followup.send("투표를 반영했습니다.", ephemeral=True)

    @discord.ui.button(label="찬성", custom_id="hawawa:suggestion:yes:v1", style=discord.ButtonStyle.success)
    async def yes(self, interaction, button):
        await self.vote(interaction, 1)

    @discord.ui.button(label="반대", custom_id="hawawa:suggestion:no:v1", style=discord.ButtonStyle.danger)
    async def no(self, interaction, button):
        await self.vote(interaction, -1)

    @discord.ui.button(label="투표 취소", custom_id="hawawa:suggestion:cancel:v1")
    async def cancel(self, interaction, button):
        await self.vote(interaction, 0)

    async def on_error(self, interaction, error, item):
        if interaction.response.is_done():
            await interaction.followup.send("투표 반영 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
        else:
            await interaction.response.send_message("투표 반영 중 오류가 발생했습니다.", ephemeral=True)


class Suggestions(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()
        self.view = None

    async def cog_load(self):
        self.view = SuggestionView(self)
        self.bot.add_view(self.view)

    def cog_unload(self):
        if self.view:
            self.view.stop()

    @app_commands.command(name="suggestion", description="건의를 승인·반려하거나 결과를 조회합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(action="approve: 승인, reject: 반려, show: 조회", message_id="건의 메시지 ID", reason="처리 사유")
    async def suggestion(self, interaction: discord.Interaction, action: Literal["approve", "reject", "show"], message_id: str, reason: app_commands.Range[str, 1, 500] = "사유 없음"):
        if not message_id.isdecimal() or not 0 < int(message_id) < 2**63:
            await interaction.response.send_message("올바른 메시지 ID를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = (interaction.guild.id, int(message_id))
        async with self.lock:
            rows = await self.store.execute("SELECT channel,status,reason FROM suggestions WHERE guild=? AND message=?", key)
            if not rows:
                await interaction.followup.send("이 서버의 건의가 아닙니다.", ephemeral=True)
                return
            channel_id, status, note = rows[0]
            if action != 'show':
                channel = interaction.guild.get_channel(channel_id)
                if not isinstance(channel, discord.TextChannel):
                    await interaction.followup.send("건의 채널이 없습니다.", ephemeral=True)
                    return
                # A failed edit leaves the DB status unchanged, allowing retry.
                moderator = discord.utils.escape_markdown(interaction.user.display_name)
                label = "✅ 승인" if action == "approve" else "⏸️ 반려"
                await channel.get_partial_message(int(message_id)).edit(content=f"**{label}**\n처리자: {moderator}\n사유: {reason}", view=None, allowed_mentions=discord.AllowedMentions.none())
                await self.store.execute("UPDATE suggestions SET status=?,reason=? WHERE guild=? AND message=?", (action, reason) + key)
                status, note = action, reason
        label = {"pending": "🕓 검토 중", "approve": "✅ 승인", "reject": "⏸️ 반려"}.get(status, status)
        await interaction.followup.send(f"상태: {label}\n사유: {note or '없음'}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
