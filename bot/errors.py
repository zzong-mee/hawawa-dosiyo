"""Private fallback errors for slash commands without a local handler."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("hawawa.commands")


class HawawaTree(app_commands.CommandTree):
    async def on_error(self, interaction, error):
        # A 10062 response means Discord has already invalidated the token
        # (for example, when the gateway delivered the interaction too late).
        # There is no valid response channel left in that case.
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, discord.NotFound):
            logger.warning("Interaction expired before an error response could be sent")
            return
        if isinstance(error, discord.NotFound):
            logger.warning("Interaction expired before an error response could be sent")
            return
        binding = getattr(interaction.command, "binding", None)
        if isinstance(binding, commands.Cog) and type(binding).cog_app_command_error is not commands.Cog.cog_app_command_error:
            return
        if isinstance(error, app_commands.MissingPermissions):
            text = "이 명령어를 실행할 권한이 없습니다."
        elif isinstance(error, app_commands.BotMissingPermissions):
            text = "봇의 채널·서버 권한이 부족합니다."
        elif isinstance(error, app_commands.CommandOnCooldown):
            text = f"{error.retry_after:.0f}초 후 다시 시도해주세요."
        elif isinstance(error, app_commands.NoPrivateMessage):
            text = "서버에서만 사용할 수 있습니다."
        else:
            logger.error("Slash command failed: %s", type(error).__name__)
            text = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
