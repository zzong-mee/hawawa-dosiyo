"""Utilities that do not require a database."""

import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands


def parse_options(text: str, maximum: int, length: int) -> list[str]:
    options = [part.strip() for part in text.split(",")]
    if not 2 <= len(options) <= maximum:
        raise ValueError(f"선택지는 ,로 구분하여 2~{maximum}개 입력해주세요.")
    if any(not option or len(option) > length for option in options):
        raise ValueError(f"각 선택지는 공백을 제외하고 1~{length}자로 입력해주세요.")
    if len(set(options)) != len(options):
        raise ValueError("중복된 선택지는 사용할 수 없습니다.")
    return options


class Utility(commands.Cog):
    @app_commands.command(name="randomteam", description="참가자를 무작위 팀으로 나눕니다.")
    @app_commands.describe(participants=",로 구분한 참가자 2~40명", teams="팀 수 (기본 2)")
    async def randomteam(
        self, interaction: discord.Interaction,
        participants: app_commands.Range[str, 1, 2000],
        teams: app_commands.Range[int, 2, 10] = 2,
    ):
        try:
            members = parse_options(participants, maximum=40, length=40)
            if teams > len(members):
                raise ValueError("팀 수는 참가자 수보다 많을 수 없습니다.")
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        random.shuffle(members)
        embed = discord.Embed(title="랜덤 팀 배정", color=discord.Color.blurple())
        for index in range(teams):
            embed.add_field(
                name=f"{index + 1}팀",
                value="\n".join(discord.utils.escape_markdown(name) for name in members[index::teams]),
                inline=False,
            )
        await interaction.response.send_message(
            embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

    @app_commands.command(name="userinfo", description="사용자 정보를 확인합니다.")
    @app_commands.describe(user="확인할 사용자 (생략하면 본인)")
    async def userinfo(self, interaction: discord.Interaction, user: discord.User | None = None):
        target = user or interaction.user
        embed = discord.Embed(title="사용자 정보", color=discord.Color.blurple())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="사용자", value=str(target), inline=False)
        embed.add_field(name="사용자 ID", value=str(target.id))
        embed.add_field(name="봇 여부", value="예" if target.bot else "아니요")
        embed.add_field(name="계정 생성일", value=discord.utils.format_dt(target.created_at, "D"))
        member = target if isinstance(target, discord.Member) else (
            interaction.guild.get_member(target.id) if interaction.guild else None
        )
        if member is not None:
            embed.add_field(name="서버 표시 이름", value=member.display_name)
            if member.joined_at is not None:
                embed.add_field(name="서버 가입일", value=discord.utils.format_dt(member.joined_at, "D"))
            roles = [role.mention for role in reversed(member.roles) if not role.is_default()]
            visible_roles = []
            for role in roles:
                if len(" ".join(visible_roles + [role])) > 950:
                    break
                visible_roles.append(role)
            role_text = " ".join(visible_roles) or "없음"
            if len(visible_roles) < len(roles):
                role_text += f"\n외 {len(roles) - len(visible_roles)}개"
            embed.add_field(name="역할", value=role_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="avatar", description="사용자의 아바타를 확인합니다.")
    @app_commands.describe(user="확인할 사용자 (생략하면 본인)", global_avatar="서버 아바타 대신 계정 아바타 표시")
    async def avatar(
        self, interaction: discord.Interaction,
        user: discord.User | None = None, global_avatar: bool = False,
    ):
        target = user or interaction.user
        if not global_avatar and interaction.guild and not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target
        asset = (target.avatar or target.default_avatar) if global_avatar else target.display_avatar
        embed = discord.Embed(title="아바타", color=discord.Color.blurple())
        embed.set_image(url=asset.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="roll", description="주사위를 굴립니다.")
    @app_commands.describe(sides="주사위 면 수 (기본 6)", count="주사위 개수 (기본 1)")
    async def roll(
        self, interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 1000] = 6,
        count: app_commands.Range[int, 1, 20] = 1,
    ):
        rolls = [random.randint(1, sides) for _ in range(count)]
        await interaction.response.send_message(
            f"🎲 {count}d{sides}: {', '.join(map(str, rolls))}\n합계: {sum(rolls)}",
            ephemeral=True,
        )

    @app_commands.command(name="vote", description="선택지 중 하나를 무작위로 고릅니다.")
    @app_commands.describe(options=",로 구분한 선택지 2~20개 (예: 치킨, 피자)")
    async def vote(self, interaction: discord.Interaction, options: app_commands.Range[str, 1, 2000]):
        try:
            choices = parse_options(options, maximum=20, length=100)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            f"선택 결과: {discord.utils.escape_markdown(random.choice(choices))}",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="poll", description="채널에 공개 투표를 만듭니다.")
    @app_commands.guild_only()
    @app_commands.describe(
        question="투표 질문", options=",로 구분한 선택지 2~10개",
        hours="진행 시간 (1~168시간, 기본 24)", multiple="복수 선택 허용 여부",
    )
    async def poll(
        self, interaction: discord.Interaction,
        question: app_commands.Range[str, 1, 300],
        options: app_commands.Range[str, 1, 2000],
        hours: app_commands.Range[int, 1, 168] = 24,
        multiple: bool = False,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return
        if not interaction.app_permissions.send_polls:
            await interaction.response.send_message("봇에 투표 만들기 권한이 필요합니다.", ephemeral=True)
            return
        try:
            choices = parse_options(options, maximum=10, length=55)
            if not question.strip():
                raise ValueError("투표 질문을 입력해주세요.")
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        poll = discord.Poll(question=question.strip(), duration=timedelta(hours=hours), multiple=multiple)
        for choice in choices:
            poll.add_answer(text=choice)
        try:
            await interaction.response.send_message(poll=poll)
        except discord.HTTPException:
            message = "투표를 만들지 못했습니다. 채널의 메시지 전송·투표 권한을 확인해주세요."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility())
