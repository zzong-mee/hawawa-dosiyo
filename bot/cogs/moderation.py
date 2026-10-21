"""Permission-controlled server moderation commands."""

import discord
from discord import app_commands
from discord.ext import commands
import logging


logger = logging.getLogger("hawawa.commands.moderation")


class Moderation(commands.Cog):
    @app_commands.command(name="clear", description="최근 메시지를 삭제합니다. 고정 메시지는 보존합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(count="확인할 최근 메시지 수 (1~100, 고정 메시지 제외)")
    async def clear(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
        if not interaction.permissions.manage_messages:
            await interaction.response.send_message("메시지 관리 권한이 필요합니다.", ephemeral=True)
            return
        permissions = interaction.app_permissions
        if permissions is None:
            await interaction.response.send_message(
                "봇의 채널 권한을 확인할 수 없습니다. 잠시 후 다시 시도해주세요.",
                ephemeral=True,
            )
            return
        if not (permissions.manage_messages and permissions.read_message_history and permissions.view_channel):
            await interaction.response.send_message(
                "봇에 채널 보기·메시지 기록 보기·메시지 관리 권한이 필요합니다.", ephemeral=True
            )
            return
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("텍스트 채널이나 스레드에서 사용해주세요.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except discord.NotFound:
            # Discord invalidates interaction tokens after a short window.
            logger.warning("Clear command interaction expired before acknowledgement")
            return
        try:
            deleted = await channel.purge(
                limit=count,
                before=interaction.created_at,
                check=lambda message: not message.pinned,
                reason=f"/clear by user {interaction.user.id}",
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "삭제 도중 오류가 발생했습니다. 일부 메시지는 이미 삭제되었을 수 있습니다. 채널 권한을 확인해주세요.",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Clear command failed while purging messages")
            await interaction.followup.send(
                "메시지를 삭제하는 중 오류가 발생했습니다. 채널 권한을 확인해주세요.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            f"최근 {count}개 범위에서 메시지 {len(deleted)}개를 삭제했습니다. 고정 메시지는 보존합니다.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation())
