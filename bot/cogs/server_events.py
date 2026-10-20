"""Configurable server event logging, suggestions, and message experience."""

import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed, text_name, channel_name, user_names, identify

from bot.storage import Store
from bot.cogs.automation import render_template

logger = logging.getLogger("hawawa.events")


class ServerEvents(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()

    @app_commands.command(name="serverconfig", description="기록·퇴장 안내·건의 채널과 경험치 기능을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(feature="설정할 기능", channel="기능 전용 채널", enabled="기능 켜기/끄기 (생략하면 조회)")
    async def serverconfig(
        self, interaction: discord.Interaction,
        feature: Literal["logs", "goodbye", "suggestions", "levels"],
        channel: discord.TextChannel | None = None, enabled: bool | None = None,
    ):
        if feature == "levels" and channel:
            await interaction.response.send_message("경험치는 채널 대신 enabled 옵션으로 설정해주세요.", ephemeral=True)
            return
        if feature == "goodbye" and enabled is not False and channel and not self.bot.intents.members:
            await interaction.response.send_message("퇴장 안내에는 Server Members Intent와 ENABLE_MEMBER_EVENTS=true가 필요합니다.", ephemeral=True)
            return
        if channel:
            permissions = channel.permissions_for(interaction.guild.me)
            if channel.guild.id != interaction.guild.id or not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                await interaction.response.send_message("봇이 메시지·임베드를 보낼 수 있는 이 서버의 채널을 선택해주세요.", ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True, thinking=True)
        current = await self.store.get(interaction.guild.id, feature)
        if enabled is False:
            current = ""
        elif feature == "levels" and enabled is True:
            current = "on"
        elif channel:
            current = str(channel.id)
        elif enabled is True and not current:
            await interaction.followup.send("채널도 함께 지정해주세요.", ephemeral=True)
            return
        if enabled is not None or channel:
            await self.store.set(interaction.guild.id, feature, current or "")
        labels = {"logs": "이벤트 로그", "goodbye": "퇴장 안내", "suggestions": "건의 채널", "levels": "경험치"}
        value = ("켜짐" if current else "꺼짐") if feature == "levels" else (channel_name(interaction.guild, current) if current else "꺼짐")
        await interaction.followup.send(f"{labels[feature]}: {value}", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def publish(self, guild, key, embed):
        value = await self.store.get(guild.id, key)
        channel = guild.get_channel(int(value)) if value else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def event(self, guild, title, description):
        try:
            kind = "danger" if "삭제" in title or "퇴장" in title else "success"
            await self.publish(guild, "logs", make_embed(title=title, description=description[:4000], kind=kind))
        except Exception:
            logger.exception("Event log failed in guild %s", guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.event(member.guild, "멤버 입장", f"**{text_name(member)}**님이 서버에 들어왔어요.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.event(member.guild, "멤버 퇴장", f"**{text_name(member)}**님이 서버를 떠났어요.")
        try:
            template = await self.store.get(member.guild.id, "goodbye_template") or "{user}님이 나갔습니다."
            await self.publish(member.guild, "goodbye", make_embed(title="퇴장 안내", description=render_template(template, member, member.guild)))
        except Exception:
            logger.exception("Goodbye message failed in guild %s", member.guild.id)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.event(channel.guild, "채널 생성", f"채널 이름: {discord.utils.escape_markdown(channel.name)}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.event(channel.guild, "채널 삭제", f"채널 이름: {discord.utils.escape_markdown(channel.name)}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.event(role.guild, "역할 생성", f"역할 이름: {text_name(role, '이름 없는 역할')}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.event(role.guild, "역할 삭제", f"역할 이름: {text_name(role, '이름 없는 역할')}")

    @app_commands.command(name="suggest", description="설정된 건의 채널에 의견을 게시합니다.")
    @app_commands.guild_only()
    @app_commands.describe(text="서버 운영자에게 건의할 내용 (공개 게시)")
    @app_commands.checks.cooldown(1, 60, key=lambda interaction: (interaction.guild_id, interaction.user.id))
    async def suggest(self, interaction: discord.Interaction, text: app_commands.Range[str, 1, 1800]):
        if not text.strip():
            await interaction.response.send_message("건의 내용을 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        value = await self.store.get(interaction.guild.id, "suggestions")
        channel = interaction.guild.get_channel(int(value)) if value else None
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("운영자가 /serverconfig로 건의 채널을 설정해야 합니다.", ephemeral=True)
            return
        # Prevent using the bot to publish in channels the author cannot view.
        if not channel.permissions_for(interaction.user).view_channel:
            await interaction.followup.send("건의 채널을 볼 수 있는 멤버만 게시할 수 있습니다.", ephemeral=True)
            return
        embed = make_embed(title="새 건의", description=text.strip(), kind="social")
        identify(embed, interaction.user)
        embed.add_field(name="🗳️ 여러분의 의견은?", value="아래 버튼으로 찬성·반대하거나 투표를 취소할 수 있어요.", inline=False)
        embed.set_footer(text="Hawawa Dosiyo · 사용자당 한 표 · 결정 후 투표 마감")
        message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        suggestions = self.bot.get_cog("Suggestions")
        if suggestions:
            await suggestions.store.execute("INSERT INTO suggestions (guild,message,channel,author) VALUES (?,?,?,?)", (interaction.guild.id, message.id, channel.id, interaction.user.id))
            await message.edit(view=suggestions.view)
        await interaction.followup.send(f"건의를 게시했습니다: {message.jump_url}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot or message.webhook_id:
            return
        try:
            if await self.store.get(message.guild.id, "levels") != "on":
                return
            now = time.time()
            rows = await self.store.execute(
                "INSERT INTO experience VALUES (?,?,10,?) ON CONFLICT(guild,user) DO UPDATE SET xp=xp+10,last=excluded.last WHERE experience.last<=? RETURNING xp",
                (message.guild.id, message.author.id, now, now - 60),
            )
            rewards = self.bot.get_cog("LevelRewards") if rows and hasattr(self.bot, 'get_cog') else None
            if rewards:
                await rewards.award(message.author, rows[0][0])
        except Exception:
            logger.exception("Experience update failed in guild %s", message.guild.id)

    @app_commands.command(name="rank", description="서버에서 획득한 경험치와 레벨을 확인합니다.")
    @app_commands.guild_only()
    async def rank(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await self.store.execute("SELECT xp FROM experience WHERE guild=? AND user=?", (interaction.guild.id, target.id))
        xp = rows[0][0] if rows else 0
        progress = xp % 100
        bar = "🟪" * (progress // 10) + "⬜" * (10 - progress // 10)
        embed = make_embed(title="경험치 프로필", description=f"**{text_name(target)}**님의 서버 활동 기록이에요.")
        identify(embed, target)
        embed.add_field(name="🏅 레벨", value=f"**Lv. {xp // 100}**")
        embed.add_field(name="💎 누적 경험치", value=f"**{xp:,} XP**")
        embed.add_field(name="🚀 다음 레벨까지", value=f"**{100 - progress} XP**")
        embed.add_field(name="진행률", value=f"{bar} **{progress}%**", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="leaderboard", description="서버 경험치 상위 10명을 확인합니다.")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await self.store.execute("SELECT user,xp FROM experience WHERE guild=? ORDER BY xp DESC,user LIMIT 10", (interaction.guild.id,))
        names = await user_names(interaction.guild, [user for user, _ in rows], self.bot)
        embed = make_embed(title="경험치 순위", description="서버에서 활약한 멤버들을 만나보세요!", kind="warning")
        medals = ["🥇", "🥈", "🥉"]
        for index, (user, xp) in enumerate(rows):
            medal = medals[index] if index < 3 else f"{index + 1}위"
            embed.add_field(name=f"{medal} {names[user]}", value=f"**Lv. {xp // 100}** · {xp:,} XP", inline=False)
        if not rows:
            embed.description = "🌱 아직 경험치 기록이 없어요. 첫 번째 주인공이 되어보세요!"
        await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def cog_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            text = f"{error.retry_after:.0f}초 후 다시 시도해주세요."
        elif isinstance(error, app_commands.MissingPermissions):
            text = "설정 변경에는 서버 관리 권한이 필요합니다."
        else:
            logger.error("Server event command failed: %s", type(error).__name__)
            text = "처리에 실패했습니다. 채널 설정과 봇 권한을 확인해주세요."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerEvents(bot))
