"""General slash commands."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.presentation import make_embed
from bot.i18n import COMMAND_NAMES

HELP_EXAMPLES = {
    "ping": "/ping", "help": "/help command:avatar",
    "serverinfo": "/serverinfo", "userinfo": "/userinfo user:@사용자",
    "avatar": "/avatar global_avatar:true", "roll": "/roll sides:6 count:2",
    "vote": "/vote options:치킨, 피자",
    "poll": "/poll question:저녁 메뉴 options:치킨, 피자 hours:24",
    "randomteam": "/randomteam participants:철수, 영희, 민수, 지수 teams:2",
    "clear": "/clear count:10",
    "charinfo": "/charinfo characters:가😀",
    "permissions": "/permissions bot:true",
    "tag": "/tag action:set name:rules content:서버 규칙을 읽어주세요",
    "welcome": "/welcome channel:#입장안내",
    "autorole": "/autorole role:@멤버",
    "reminder": "/reminder action:생성 name:약속 text:약속 확인 mode:타이머 timer:30 · 또는 mode:알림 alert:09:30",
    "rolepanel": "/rolepanel role:@게임알림 title:알림 역할 선택",
    "rolepaneldisable": "/rolepaneldisable message_id:패널메시지ID",
    "serverconfig": "/serverconfig feature:suggestions channel:#건의 enabled:true",
    "suggest": "/suggest text:주말에 게임 모임을 열어요",
    "rank": "/rank", "leaderboard": "/leaderboard",
    "automod": "/automod kind:keywords action:set words:차단단어1, 차단단어2",
    "temprole": "/temprole member:@사용자 role:@체험멤버 minutes:60",
    "giveaway": "/giveaway action:create prize:참가자 추첨 minutes:60 winners:1",
    "starboard": "/starboard channel:#추천 minimum:3",
    "modcase": "/modcase action:warn member:@사용자 reason:규칙 위반",
    "trigger": "/trigger action:set keyword:안녕 response:{user}님, 환영합니다",
    "embed": "/embed title:공지 text:{server}의 규칙을 읽어주세요",
    "roleautomation": "/roleautomation action:delay role:@멤버 minutes:60",
    "coinflip": "/coinflip", "rps": "/rps choice:가위",
    "members": "/members order:newjoins count:10",
    "greetingtemplate": "/greetingtemplate kind:welcome text:{server}에 오신 {user}님 환영합니다",
    "sticky": "/sticky text:채팅 전 서버 규칙을 확인해주세요",
    "suggestion": "/suggestion action:approve message_id:건의메시지ID reason:반영 예정",
    "levelreward": "/levelreward action:set level:5 role:@활동멤버",
    "stocks": "/stocks", "stockbuy": "/stockbuy symbol:HAWA mode:수량 지정 quantity:10",
    "stocksell": "/stocksell symbol:HAWA mode:수량 지정 quantity:10", "portfolio": "/portfolio",
}


class HelpPages(discord.ui.View):
    def __init__(self, pages, owner):
        super().__init__(timeout=180)
        self.pages = pages
        self.owner = owner
        self.index = 0
        self.children[0].disabled = True

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner:
            return True
        await interaction.response.send_message("도움말을 다시 실행해주세요.", ephemeral=True)
        return False

    async def move(self, interaction, delta):
        self.index = min(max(0, self.index + delta), len(self.pages) - 1)
        self.children[0].disabled = self.index == 0
        self.children[1].disabled = self.index == len(self.pages) - 1
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction, button):
        await self.move(interaction, -1)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.primary)
    async def following(self, interaction, button):
        await self.move(interaction, 1)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="봇 연결 상태를 확인합니다.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"퐁! {round(self.bot.latency * 1000)}ms", ephemeral=True
        )

    @app_commands.command(name="help", description="사용 가능한 명령어를 확인합니다.")
    @app_commands.describe(command="자세히 볼 명령어 이름 (예: avatar, 생략하면 전체 목록)")
    async def help(self, interaction: discord.Interaction, command: str | None = None):
        commands_list = sorted(self.bot.tree.get_commands(), key=lambda item: item.name)
        if command is not None:
            name = command.strip().lstrip("/").lower()
            name = next((english for english, korean in COMMAND_NAMES.items() if korean == name), name)
            selected = next((item for item in commands_list if item.name == name), None)
            if selected is None:
                await interaction.response.send_message(
                    "없는 명령어입니다. /help에서 목록을 확인해주세요.", ephemeral=True
                )
                return
            korean_name = COMMAND_NAMES.get(selected.name, selected.name)
            embed = make_embed(title=f"/{korean_name}", description=f"실행 명령어: `/{selected.name}`\n{selected.description}")
            if isinstance(selected, app_commands.Group):
                for child in selected.commands:
                    child_name = COMMAND_NAMES.get(child.name, child.name)
                    embed.add_field(name=f"/{korean_name} {child_name}", value=f"`/{selected.name} {child.name}` — {child.description}", inline=False)
            for parameter in getattr(selected, "parameters", ()):
                status = "필수" if parameter.required else "선택"
                detail = parameter.description
                if parameter.choices:
                    detail += "\n선택: " + ", ".join(str(choice.value) for choice in parameter.choices)
                if not parameter.required:
                    detail += f"\n기본값: {parameter.default if parameter.default is not None else '생략 가능'}"
                embed.add_field(name=f"{parameter.name} ({status})", value=detail, inline=False)
            embed.add_field(name="사용 예시", value=f"`/{korean_name}` (영문 환경: `/{HELP_EXAMPLES.get(name, name)}`)", inline=False)
            if selected.guild_only:
                embed.add_field(name="사용 위치", value="서버 전용", inline=False)
            if name == "clear":
                embed.add_field(name="주의", value="메시지 관리 권한 필요. 고정 메시지는 보존하며 삭제는 되돌릴 수 없습니다.", inline=False)
            if name in ("welcome", "autorole"):
                embed.add_field(name="설정 조건", value="입장 이벤트 활성화 필요. welcome은 서버 관리, autorole은 역할 관리 권한이 필요합니다.", inline=False)
            if name == "tag":
                embed.add_field(name="수정 권한", value="조회·목록은 누구나 사용 가능하며 저장·삭제에는 서버 관리 권한이 필요합니다.", inline=False)
            if name in ("rolepanel", "rolepaneldisable"):
                embed.add_field(name="권한", value="역할 관리 권한 필요. 관리 권한이 없는 일반 역할만 공개 지급할 수 있습니다.", inline=False)
            if name == "reminder":
                embed.add_field(name="안내", value="알림은 DM으로 보냅니다. DM을 허용해주세요. 최대 25개, 생성한 서버에서 조회·취소합니다.", inline=False)
            if name == "temprole":
                embed.add_field(name="권한", value="역할 관리 권한 필요. 기존 일반 역할은 회수 예약하지 않습니다. 재시작 후 만료된 역할을 회수합니다.", inline=False)
            if name in ("giveaway", "starboard"):
                embed.add_field(name="권한", value="설정·운영 명령에는 서버 관리 권한이 필요합니다. 추첨 참가는 공개 버튼을 사용합니다.", inline=False)
            embed.set_footer(text="응답은 본인에게만 표시됩니다. 투표·건의·역할 패널·서버 이벤트 안내는 채널에 게시됩니다.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = make_embed(
            title="Hawawa Dosiyo 명령어",
            description="Discord 언어가 한국어면 아래 이름으로 표시됩니다. 실제 입력은 괄호 안 영어 이름도 사용할 수 있어요.\n여러 선택지·참가자는 쉼표(,)로 구분합니다.",

        )
        categories = {"General": "기본", "Utility": "유틸리티", "Information": "정보 조회", "Moderation": "서버 관리", "Community": "서버 운영", "Reminders": "리마인더", "RolePanels": "버튼 역할", "ServerEvents": "서버 활동", "AutoModeration": "자동 관리", "TemporaryRoles": "기간 역할", "Giveaways": "추첨", "Starboard": "추천 게시판", "ModerationRecords": "관리 기록", "Automation": "자동 응답·안내", "RoleAutomation": "역할 자동화", "Extras": "게임·멤버 조회", "Announcements": "안내 문구", "Suggestions": "건의 관리", "LevelRewards": "레벨 보상", "Stocks": "주식 미니게임"}
        for cog_name, label in categories.items():
            entries = [f"`/{COMMAND_NAMES.get(item.name, item.name)}` (`/{item.name}`) — {item.description}" for item in commands_list if getattr(getattr(item, "binding", None), "qualified_name", None) == cog_name or (cog_name == "Reminders" and item.name == "reminder")]
            if entries:
                embed.add_field(name=label, value="\n".join(entries), inline=False)
        others = [item for item in commands_list if getattr(getattr(item, "binding", None), "qualified_name", None) not in categories and item.name != "reminder"]
        for item in others:
            embed.add_field(
                name=f"/{COMMAND_NAMES.get(item.name, item.name)} (`/{item.name}`)", value=f"`/{item.name}` — {item.description}", inline=False
            )
        embed.set_footer(text="/serverinfo·/poll·/clear·/permissions는 서버 전용이며, /clear는 메시지 관리 권한이 필요합니다.")
        pages = []
        fields = list(embed.fields)
        for start in range(0, len(fields), 6):
            page = make_embed(title=embed.title, description=embed.description, color=embed.color)
            for field in fields[start:start + 6]:
                page.add_field(name=field.name, value=field.value, inline=False)
            page.set_footer(text=f"{len(pages) + 1}/{(len(fields) + 5) // 6} · 자세한 사용법: /help command:명령어")
            pages.append(page)
        if len(pages) > 1:
            view = HelpPages(pages, interaction.user.id)
            await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="현재 서버 정보를 확인합니다.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "서버에서만 사용할 수 있는 명령어입니다.", ephemeral=True
            )
            return

        embed = make_embed(title="서버 정보")
        embed.description = "우리 서버의 기본 정보를 한눈에 확인하세요."
        icon_url = getattr(getattr(guild, "icon", None), "url", None)
        if isinstance(icon_url, str):
            embed.set_thumbnail(url=icon_url)
        embed.add_field(name="서버 이름", value=guild.name, inline=False)
        member_count = guild.member_count
        embed.add_field(
            name="멤버 수",
            value=f"{member_count:,}명" if member_count is not None else "확인할 수 없음",
        )
        embed.add_field(
            name="생성일", value=discord.utils.format_dt(guild.created_at, style="D")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
