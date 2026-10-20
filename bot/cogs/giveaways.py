"""Persistent opt-in giveaways with durable results and idempotent announcements."""

import asyncio
import json
import logging
import secrets
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.presentation import make_embed, user_names

from bot.storage import Store

logger = logging.getLogger("hawawa.giveaways")


class GiveawayView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def update_entry(self, interaction, join):
        if interaction.guild is None or interaction.message is None or interaction.user.bot:
            await interaction.response.send_message("서버의 추첨 메시지에서 사용해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild, message, user = interaction.guild.id, interaction.message.id, interaction.user.id
        async with self.cog.lock:
            rows = await self.cog.store.execute("SELECT due,result FROM giveaways WHERE guild=? AND message=?", (guild, message))
            if not rows or rows[0][1] is not None or rows[0][0] <= time.time():
                await interaction.followup.send("마감된 추첨입니다.", ephemeral=True)
                return
            if join:
                await self.cog.store.execute("INSERT OR IGNORE INTO giveaway_entries VALUES (?,?,?)", (guild, message, user))
            else:
                await self.cog.store.execute("DELETE FROM giveaway_entries WHERE guild=? AND message=? AND user=?", (guild, message, user))
        await interaction.followup.send("참가했습니다." if join else "참가를 취소했습니다.", ephemeral=True)

    @discord.ui.button(label="참가", custom_id="hawawa:giveaway:join:v1", style=discord.ButtonStyle.success)
    async def join(self, interaction, button):
        await self.update_entry(interaction, True)

    @discord.ui.button(label="참가 취소", custom_id="hawawa:giveaway:leave:v1")
    async def leave(self, interaction, button):
        await self.update_entry(interaction, False)

    async def on_error(self, interaction, error, item):
        logger.error("Giveaway button failed: %s", type(error).__name__)
        if interaction.response.is_done():
            await interaction.followup.send("참가 처리에 실패했습니다. 다시 시도해주세요.", ephemeral=True)
        else:
            await interaction.response.send_message("참가 처리에 실패했습니다.", ephemeral=True)


class Giveaways(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()
        self.view = None

    async def cog_load(self):
        self.view = GiveawayView(self)
        self.bot.add_view(self.view)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.finish.is_running():
            self.finish.start()

    def cog_unload(self):
        self.finish.cancel()
        if self.view:
            self.view.stop()

    @app_commands.command(name="giveaway", description="버튼 참가 추첨을 생성·조회·마감합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(action="create: 생성, list: 목록, end: 마감, reroll: 재추첨", prize="경품·추첨 제목", minutes="진행 시간 (1분~30일)", winners="당첨 인원", message_id="마감·재추첨할 추첨 메시지 ID")
    async def giveaway(
        self, interaction: discord.Interaction,
        action: Literal["create", "list", "end", "reroll"],
        prize: app_commands.Range[str, 1, 200] | None = None,
        minutes: app_commands.Range[int, 1, 43200] = 60,
        winners: app_commands.Range[int, 1, 10] = 1,
        message_id: str | None = None,
    ):
        if action == "create" and (not prize or not prize.strip() or not isinstance(interaction.channel, discord.TextChannel)):
            await interaction.response.send_message("텍스트 채널에서 경품 제목을 입력해주세요.", ephemeral=True)
            return
        if action in ("end", "reroll") and (not message_id or not message_id.isdecimal() or not 0 < int(message_id) < 2**63):
            await interaction.response.send_message("올바른 추첨 메시지 ID를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild.id
        if action == "create":
            permissions = interaction.app_permissions
            if not (permissions.send_messages and permissions.embed_links and permissions.view_channel):
                await interaction.followup.send("봇에 메시지 전송·임베드·채널 보기 권한이 필요합니다.", ephemeral=True)
                return
            due = time.time() + minutes * 60
            embed = make_embed(title="참가자 추첨", description=f"**{prize.strip()}**\n\n아래 참가 버튼을 눌러 행운의 주인공이 되어보세요!", kind="warning")
            embed.add_field(name="⏳ 마감", value=f"<t:{int(due)}:R>")
            embed.add_field(name="🏆 당첨 인원", value=f"**{winners}명**")
            message = await interaction.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            await self.store.execute("INSERT INTO giveaways (guild,message,channel,prize,due,count) VALUES (?,?,?,?,?,?)", (guild, message.id, message.channel.id, prize.strip(), due, winners))
            await message.edit(view=self.view)
            text = f"추첨을 만들었습니다. 메시지 ID: {message.id}"
        elif action == "list":
            rows = await self.store.execute("SELECT message,due FROM giveaways WHERE guild=? AND result IS NULL ORDER BY due LIMIT 20", (guild,))
            text = "\n".join(f"{message} · <t:{int(due)}:R>" for message, due in rows) or "진행 중인 추첨이 없습니다."
        elif action == "reroll":
            async with self.lock:
                rows = await self.store.execute("SELECT count,result FROM giveaways WHERE guild=? AND message=? AND result IS NOT NULL AND due>?", (guild, int(message_id), time.time() - 30 * 86400))
                if not rows:
                    text = "30일 이내에 마감한 이 서버의 추첨을 선택해주세요."
                else:
                    previous = set(json.loads(rows[0][1]))
                    entries = await self.store.execute("SELECT user FROM giveaway_entries WHERE guild=? AND message=?", (guild, int(message_id)))
                    pool = [row[0] for row in entries if row[0] not in previous]
                    if not pool:
                        text = "기존 당첨자를 제외한 참가자가 없습니다."
                    else:
                        result = secrets.SystemRandom().sample(pool, min(rows[0][0], len(pool)))
                        await self.store.execute("UPDATE giveaways SET result=?,announced=0,due=? WHERE guild=? AND message=?", (json.dumps(result), time.time(), guild, int(message_id)))
                        text = "직전 당첨자를 제외하고 재추첨했습니다. 15초 이내 원본 메시지에 반영됩니다."
        else:
            rows = await self.store.execute("UPDATE giveaways SET due=? WHERE guild=? AND message=? AND result IS NULL RETURNING message", (time.time(), guild, int(message_id)))
            text = "마감을 예약했습니다. 15초 이내 결과가 반영됩니다." if rows else "진행 중인 이 서버의 추첨이 아닙니다."
        await interaction.followup.send(text, ephemeral=True)

    async def finish_once(self, now=None):
        now = time.time() if now is None else now
        async with self.lock:
            rows = await self.store.execute("SELECT guild,message,channel,prize,count,result FROM giveaways WHERE due<=? AND announced=0 LIMIT 20", (now,))
            for guild_id, message_id, channel_id, prize, count, result in rows:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild is None:
                        continue
                    channel = guild.get_channel(channel_id)
                    if not isinstance(channel, discord.TextChannel):
                        continue
                    if result is None:
                        entries = await self.store.execute("SELECT user FROM giveaway_entries WHERE guild=? AND message=?", (guild_id, message_id))
                        # Freeze and save results before editing the original message.
                        selected = secrets.SystemRandom().sample([entry[0] for entry in entries], min(count, len(entries)))
                        result = json.dumps(selected)
                        await self.store.execute("UPDATE giveaways SET result=? WHERE guild=? AND message=? AND result IS NULL", (result, guild_id, message_id))
                    winners = json.loads(result)
                    names = await user_names(guild, winners, self.bot)
                    embed = make_embed(title="추첨 마감", description=f"**{prize}**\n추첨 결과를 발표합니다!", kind="success")
                    embed.add_field(name="🎉 당첨자", value="\n".join(f"🥳 **{names[user]}**" for user in winners) or "참가자가 없습니다.", inline=False)
                    await channel.get_partial_message(message_id).edit(embed=embed, view=None, allowed_mentions=discord.AllowedMentions.none())
                    await self.store.execute("UPDATE giveaways SET announced=1 WHERE guild=? AND message=?", (guild_id, message_id))
                except discord.NotFound:
                    await self.store.execute("UPDATE giveaways SET announced=-1 WHERE guild=? AND message=?", (guild_id, message_id))
                except discord.HTTPException:
                    logger.warning("Giveaway result delivery failed in guild %s", guild_id)
            await self.store.execute("DELETE FROM giveaway_entries WHERE EXISTS (SELECT 1 FROM giveaways WHERE giveaways.guild=giveaway_entries.guild AND giveaways.message=giveaway_entries.message AND giveaways.result IS NOT NULL AND giveaways.due<?)", (now - 30 * 86400,))

    @tasks.loop(seconds=15)
    async def finish(self):
        try:
            await self.finish_once()
        except Exception:
            logger.exception("Giveaway completion failed")

    async def cog_app_command_error(self, interaction, error):
        logger.error("Giveaway command failed: %s", type(error).__name__)
        text = "서버 관리 권한이 필요하거나 추첨 처리에 실패했습니다."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
