"""Character and channel permission inspection."""

import unicodedata

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed


class Information(commands.Cog):
    @app_commands.command(name="charinfo", description="문자의 Unicode 코드와 이름을 확인합니다.")
    @app_commands.describe(characters="확인할 문자 (최대 15개, 이모지는 여러 문자로 구성될 수 있음)")
    async def charinfo(
        self, interaction: discord.Interaction,
        characters: app_commands.Range[str, 1, 15],
    ):
        # Discord string length and Python code point length may differ for emoji.
        if not 1 <= len(characters) <= 15:
            await interaction.response.send_message("문자는 Unicode 코드 포인트 기준 1~15개 입력해주세요.", ephemeral=True)
            return
        embed = make_embed(title="문자 정보", description="보이지 않는 문자까지 코드 포인트별로 살펴보세요.", kind="social")
        for character in characters:
            code = f"U+{ord(character):04X}"
            name = unicodedata.name(character, "이름 없는 문자")
            embed.add_field(
                name=code,
                value=f"이름: {name}\nPython 표기: `{ascii(character)}`",
                inline=False,
            )
        embed.set_footer(text="결합 이모지는 여러 코드 포인트로 나누어 표시됩니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="permissions", description="현재 채널에서 사용자 또는 봇의 적용 권한을 확인합니다.")
    @app_commands.guild_only()
    @app_commands.describe(member="확인할 멤버 (생략하면 본인)", bot="봇 자신의 권한 확인 (멤버 옵션과 함께 사용 불가)")
    async def permissions(
        self, interaction: discord.Interaction,
        member: discord.Member | None = None, bot: bool = False,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
        if bot and member is not None:
            await interaction.response.send_message("member와 bot 옵션 중 하나만 선택해주세요.", ephemeral=True)
            return
        if bot:
            target_name = "Hawawa Dosiyo"
            permissions = interaction.app_permissions
        elif member is None or member.id == interaction.user.id:
            target_name = interaction.user.display_name
            permissions = interaction.permissions
        else:
            channel = interaction.channel
            if member.guild.id != interaction.guild.id or not isinstance(
                channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.Thread)
            ):
                await interaction.response.send_message("이 채널에서는 해당 멤버의 권한을 확인할 수 없습니다.", ephemeral=True)
                return
            target_name = member.display_name
            permissions = channel.permissions_for(member)

        labels = {
            "view_channel": "채널 보기", "read_message_history": "메시지 기록 보기",
            "send_messages": "메시지 보내기", "send_messages_in_threads": "스레드에서 메시지 보내기",
            "embed_links": "링크 임베드", "attach_files": "파일 첨부",
            "add_reactions": "반응 추가", "send_polls": "투표 만들기",
            "manage_messages": "메시지 관리", "manage_channels": "채널 관리",
            "manage_roles": "역할 관리", "moderate_members": "멤버 타임아웃",
            "connect": "음성 연결", "speak": "음성 발언", "administrator": "관리자",
        }
        embed = make_embed(title="현재 채널 권한", description="허용된 권한과 제한된 권한을 나누어 표시했어요.")
        embed.add_field(name="대상", value=discord.utils.escape_markdown(target_name), inline=False)
        allowed = [f"✅ {label}" for key, label in labels.items() if getattr(permissions, key)]
        denied = [f"❌ {label}" for key, label in labels.items() if not getattr(permissions, key)]
        embed.add_field(name="🟢 허용 권한", value="\n".join(allowed) or "해당 없음", inline=True)
        embed.add_field(name="🔴 제한 권한", value="\n".join(denied) or "제한 없음", inline=True)
        embed.set_footer(text="현재 채널 기준입니다. 역할 서열·스레드 상태 등에 따라 실제 작업이 제한될 수 있습니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Information())
