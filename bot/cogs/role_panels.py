"""Persistent button roles backed by server/message-specific configuration."""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed, text_name

from bot.cogs.community import safe_role
from bot.storage import Store

logger = logging.getLogger("hawawa.roles")


class RolePanel(discord.ui.View):
    def __init__(self, store):
        super().__init__(timeout=None)
        self.store = store
        self.lock = asyncio.Lock()

    @discord.ui.button(label="역할 받기 / 해제", style=discord.ButtonStyle.primary, custom_id="hawawa:role:toggle:v1")
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("서버 역할 패널에서 사용해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.lock:
            rows = await self.store.execute(
                "SELECT role FROM role_panels WHERE guild=? AND message=? AND enabled=1", (interaction.guild.id, interaction.message.id))
            role = interaction.guild.get_role(rows[0][0]) if rows else None
            if role is None or not safe_role(interaction.guild, role):
                await interaction.followup.send("비활성화되었거나 지급할 수 없는 역할입니다.", ephemeral=True)
                return
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
                remove = role in member.roles
                if remove:
                    await member.remove_roles(role, reason="Self-service role panel")
                else:
                    await member.add_roles(role, reason="Self-service role panel")
            except discord.HTTPException:
                await interaction.followup.send("역할을 변경하지 못했습니다. 봇 권한과 역할 순서를 확인해주세요.", ephemeral=True)
                return
        await interaction.followup.send("역할을 해제했습니다." if remove else "역할을 지급했습니다.", ephemeral=True)

    async def on_error(self, interaction, error, item):
        logger.error("Role panel failed: %s", type(error).__name__)
        if interaction.response.is_done():
            await interaction.followup.send("역할 처리 중 오류가 발생했습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("역할 처리 중 오류가 발생했습니다.", ephemeral=True)


class RolePanels(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()
        self.view = None

    async def cog_load(self):
        self.view = RolePanel(self.store)
        self.bot.add_view(self.view)

    def cog_unload(self):
        if self.view:
            self.view.stop()

    @app_commands.command(name="rolepanel", description="버튼으로 역할을 받거나 해제하는 패널을 만듭니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(role="누구나 받을 수 있는 일반 역할", title="패널 제목")
    async def rolepanel(self, interaction: discord.Interaction, role: discord.Role, title: app_commands.Range[str, 1, 100] = "역할 선택"):
        if not safe_role(interaction.guild, role) or (
            interaction.user.id != interaction.guild.owner_id and role >= interaction.user.top_role
        ):
            await interaction.response.send_message("관리 권한이 없는 일반 역할이며 실행자와 봇보다 낮은 역할을 선택해주세요.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("서버 텍스트 채널에서 사용해주세요.", ephemeral=True)
            return
        permissions = interaction.app_permissions
        if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message("봇에 채널 보기·메시지 전송·임베드 권한이 필요합니다.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Publish without an active button until the configuration is durable.
        message = await interaction.channel.send(
            embed=make_embed(title=f"🎭 {title}", description=f"**{text_name(role, '일반 역할')}**\n\n아래 버튼을 눌러 역할을 받으세요.\n다시 누르면 역할을 해제할 수 있어요.", kind="social"),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await self.store.execute("INSERT INTO role_panels (guild,message,role) VALUES (?,?,?)", (interaction.guild.id, message.id, role.id))
        await message.edit(view=self.view)
        await interaction.followup.send(f"역할 패널을 만들었습니다. 메시지 ID: {message.id}", ephemeral=True)

    @app_commands.command(name="rolepaneldisable", description="역할 패널을 비활성화합니다.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(message_id="해제할 패널 메시지 ID")
    async def disable(self, interaction: discord.Interaction, message_id: str):
        if not message_id.isdecimal() or not 0 < int(message_id) < 2**63:
            await interaction.response.send_message("올바른 메시지 ID를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await self.store.execute("UPDATE role_panels SET enabled=0 WHERE guild=? AND message=? RETURNING message", (interaction.guild.id, int(message_id)))
        await interaction.followup.send("패널을 비활성화했습니다. 이미 지급된 역할은 유지됩니다." if rows else "이 서버의 패널이 아닙니다.", ephemeral=True)

    async def cog_app_command_error(self, interaction, error):
        logger.error("Role panel command failed: %s", type(error).__name__)
        text = "역할 패널 처리에 실패했습니다. 역할 관리 권한과 봇의 채널 권한을 확인해주세요."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanels(bot))
