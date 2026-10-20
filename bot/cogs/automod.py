"""Configure Discord-native blocking rules without reading message content."""

import asyncio
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands


class AutoModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    @app_commands.command(name="automod", description="Discord 기본 금칙어·멘션 도배 차단을 설정합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(kind="규칙 종류", action="show: 조회, set: 활성화/변경, disable: 비활성화", words="쉼표로 구분한 차단 단어 (set 시 기존 목록 대체)", mentions="멘션 허용 개수 (기본 5)")
    async def automod(
        self, interaction: discord.Interaction,
        kind: Literal["keywords", "mentions"],
        action: Literal["show", "set", "disable"],
        words: app_commands.Range[str, 1, 2000] | None = None,
        mentions: app_commands.Range[int, 1, 50] = 5,
    ):
        if not interaction.app_permissions.manage_guild:
            await interaction.response.send_message("봇에도 서버 관리 권한이 필요합니다.", ephemeral=True)
            return
        keywords = [word.strip() for word in words.split(",")] if words else []
        if action == "set" and kind == "keywords" and (
            not 1 <= len(keywords) <= 100 or any(not word or len(word) > 60 for word in keywords)
        ):
            await interaction.response.send_message("차단 단어를 쉼표로 구분해 1~100개 입력해주세요. 각 단어는 1~60자입니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        name = f"Hawawa:{self.bot.user.id}:{kind}"
        try:
            async with self.lock:
                rules = await interaction.guild.fetch_automod_rules()
                rule = next((rule for rule in rules if rule.name == name and rule.creator_id == self.bot.user.id), None)
                reason = f"/automod by {interaction.user.id}"
                if action == "show":
                    text = f"{kind}: {'켜짐' if rule and rule.enabled else '꺼짐'}"
                elif action == "disable":
                    if rule:
                        await rule.edit(enabled=False, reason=reason)
                    text = "Hawawa의 해당 규칙을 비활성화했습니다. 다른 규칙은 유지됩니다."
                else:
                    trigger = discord.AutoModTrigger(keyword_filter=list(dict.fromkeys(keywords))) if kind == "keywords" else discord.AutoModTrigger(mention_limit=mentions)
                    if rule:
                        await rule.edit(trigger=trigger, enabled=True, reason=reason)
                    else:
                        await interaction.guild.create_automod_rule(
                            name=name, event_type=discord.AutoModRuleEventType.message_send,
                            trigger=trigger, actions=[discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)],
                            enabled=True, reason=reason,
                        )
                    text = "차단 규칙을 활성화했습니다. 예외 대상과 세부 설정은 Discord 서버 설정의 AutoMod에서 확인하세요."
        except discord.HTTPException:
            text = "규칙을 처리하지 못했습니다. 봇의 서버 관리 권한과 Discord 규칙 개수 제한을 확인해주세요."
        await interaction.followup.send(text, ephemeral=True)

    async def cog_app_command_error(self, interaction, error):
        text = "서버 관리 권한이 필요하거나 자동 관리 처리에 실패했습니다."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModeration(bot))
