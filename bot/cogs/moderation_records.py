"""Server-scoped warnings with reversible revocation and moderator history."""

import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from bot.storage import Store


class ModerationRecords(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()

    @app_commands.command(name="modcase", description="경고를 기록·조회·취소합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(action="warn: 경고, list: 최근 기록, show: 개별 기록, revoke: 경고 취소", member="경고 또는 조회 대상", reason="경고 사유", case_id="조회·취소할 기록 번호")
    async def modcase(
        self, interaction: discord.Interaction, action: Literal["warn", "list", "show", "revoke"],
        member: discord.Member | None = None,
        reason: app_commands.Range[str, 1, 1000] | None = None,
        case_id: int | None = None,
    ):
        if action == "warn":
            if member is None or not reason or not reason.strip():
                await interaction.response.send_message("경고 대상과 사유를 입력해주세요.", ephemeral=True)
                return
            if member.guild.id != interaction.guild.id or member.id in (interaction.user.id, interaction.guild.owner_id) or (
                interaction.user.id != interaction.guild.owner_id and member.top_role >= interaction.user.top_role
            ):
                await interaction.response.send_message("본인·서버 소유자·같거나 높은 역할의 멤버는 경고할 수 없습니다.", ephemeral=True)
                return
        if action in ("show", "revoke") and case_id is None:
            await interaction.response.send_message("case_id를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild.id
        if action == "warn":
            rows = await self.store.execute("INSERT INTO moderation_cases(guild,user,moderator,reason,created) VALUES (?,?,?,?,?) RETURNING id", (guild, member.id, interaction.user.id, reason.strip(), time.time()))
            text = f"경고 #{rows[0][0]}를 기록했습니다."
        elif action == "revoke":
            rows = await self.store.execute("UPDATE moderation_cases SET revoked=? WHERE guild=? AND id=? AND revoked=0 RETURNING id", (interaction.user.id, guild, case_id))
            text = "경고를 취소했습니다. 원본 사유·처리자와 취소자 ID는 기록에 남습니다." if rows else "활성 상태인 이 서버의 기록이 아닙니다."
        else:
            query = "SELECT id,user,moderator,reason,created,revoked FROM moderation_cases WHERE guild=?"
            args = (guild,)
            if action == "show":
                query += " AND id=?"
                args += (case_id,)
            elif member:
                query += " AND user=?"
                args += (member.id,)
            rows = await self.store.execute(query + " ORDER BY id DESC LIMIT 10", args)
            embed = discord.Embed(title="관리 기록", color=discord.Color.blurple())
            for identifier, user, moderator, note, created, revoked in rows:
                embed.add_field(name=f"#{identifier} · 사용자 {user}"[:256], value=f"처리자: {moderator} · <t:{int(created)}:f>\n{'취소자: ' + str(revoked) if revoked else '유효한 경고'}\n{note[:350]}", inline=False)
            if not rows:
                embed.description = "기록이 없습니다."
            await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return
        await interaction.followup.send(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationRecords(bot))
