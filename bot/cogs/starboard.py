"""A link-only starboard for publicly visible text channels."""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed, channel_name

from bot.storage import Store

logger = logging.getLogger("hawawa.starboard")


class Starboard(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.lock = asyncio.Lock()

    @app_commands.command(name="starboard", description="별 반응이 모인 공개 메시지를 게시할 채널을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="추천 게시판 채널", minimum="필요한 별 반응 수", disable="추천 게시판 끄기")
    async def starboard(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None, minimum: app_commands.Range[int, 1, 100] = 3, disable: bool = False):
        if channel and disable:
            await interaction.response.send_message("채널과 disable을 동시에 지정할 수 없습니다.", ephemeral=True)
            return
        if channel:
            permissions = channel.permissions_for(interaction.guild.me)
            if channel.guild.id != interaction.guild.id or not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                await interaction.response.send_message("봇이 메시지·임베드를 보낼 수 있는 이 서버의 채널을 선택해주세요.", ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.lock:
            if channel or disable:
                # Write the threshold before enabling the destination channel.
                await self.store.set(interaction.guild.id, "starboard_minimum", str(minimum))
                await self.store.set(interaction.guild.id, "starboard", str(channel.id) if channel else "")
            value = await self.store.get(interaction.guild.id, "starboard")
            threshold = await self.store.get(interaction.guild.id, "starboard_minimum") or "3"
        await interaction.followup.send(f"추천 게시판: {channel_name(interaction.guild, value)} · ⭐ {threshold}개" if value else "추천 게시판이 꺼져 있습니다.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def update(self, payload):
        if payload.guild_id is None or str(payload.emoji) != "⭐":
            return
        async with self.lock:
            guild = self.bot.get_guild(payload.guild_id)
            if guild is None:
                return
            value = await self.store.get(guild.id, "starboard")
            if not value or payload.channel_id == int(value):
                return
            source = guild.get_channel(payload.channel_id)
            destination = guild.get_channel(int(value))
            if not isinstance(source, discord.TextChannel) or not isinstance(destination, discord.TextChannel):
                return
            if not source.permissions_for(guild.default_role).view_channel:
                return
            message = await source.fetch_message(payload.message_id)
            if message.author.bot:
                return
            stars = next((reaction.count for reaction in message.reactions if str(reaction.emoji) == "⭐"), 0)
            threshold = int(await self.store.get(guild.id, "starboard_minimum") or "3")
            rows = await self.store.execute("SELECT channel,post FROM star_posts WHERE guild=? AND source=?", (guild.id, message.id))
            if not rows and stars < threshold:
                return
            embed = make_embed(title=f"⭐ {stars} · 커뮤니티 추천", description=f"[💬 원본 메시지 보러 가기]({message.jump_url})", color=discord.Color.gold())
            embed.set_footer(text="Hawawa Dosiyo · 본문과 첨부파일은 복사하지 않아요")
            if rows:
                old_channel = guild.get_channel(rows[0][0])
                if isinstance(old_channel, discord.TextChannel):
                    try:
                        await old_channel.get_partial_message(rows[0][1]).edit(embed=embed)
                    except discord.NotFound:
                        await self.store.execute("DELETE FROM star_posts WHERE guild=? AND source=?", (guild.id, message.id))
                return
            post = await destination.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            await self.store.execute("INSERT OR IGNORE INTO star_posts VALUES (?,?,?,?)", (guild.id, message.id, destination.id, post.id))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        try:
            await self.update(payload)
        except Exception:
            logger.exception("Starboard update failed")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.on_raw_reaction_add(payload)

    async def cog_app_command_error(self, interaction, error):
        text = "추천 게시판 설정에는 서버 관리 권한이 필요하거나 설정 처리에 실패했습니다."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Starboard(bot))
