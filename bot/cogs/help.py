import discord
from discord import app_commands
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="도움말", description="구렁이 봇의 모든 사용법과 카테고리를 확인합니다.")
    async def help(self, interaction: discord.Interaction):
        # 1. 원하는 출력 순서대로 Cog 클래스 이름을 나열합니다.
        preferred_order = [
            "VirtualStock",   # 주식 시뮬레이션
            "DailyCheck",     # 출석 체크 (추가됨)
            "Music",          # 음악 재생
            "Utility",        # 유틸리티
            "Help",           # 도움말
            "Clear",          # 메시지 청소 (관리자)
            "ServerSettings", # 서버 설정 (관리자)
            "Logs"            # 서버 관리 & 로그
        ]

        # 2. 카테고리 이름 및 이모지 매핑
        categories = {
            "VirtualStock": "📈 **주식 시뮬레이션**",
            "DailyCheck": "📅 **출석 체크**",
            "Music": "🎵 **음악 재생**",
            "Logs": "📜 **서버 관리 & 로그**",
            "Utility": "🛠️ **유틸리티**",
            "ServerSettings": "⚙️ **서버 설정 (관리자)**", 
            "Help": "❓ **도움말**",
            "Clear": "🧹 **메시지 청소 (관리자)**"
        }

        embed = discord.Embed(
            title="🐍 구렁이 봇 명령어 가이드",
            description=(
                "모든 명령어는 슬래시(`/`)를 입력하여 사용할 수 있습니다.\n"
                "주가는 **10분마다** 변동되며, 실시간 뉴스에 따라 시세가 바뀝니다!"
            ),
            color=discord.Color.from_rgb(46, 204, 113) # 구렁이 초록색
        )
        
        if self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # 관리자 카테고리 설정 (🛡️ 표시용)
        admin_categories = ["ServerSettings", "Clear"]

        # 3. 지정한 순서(preferred_order)대로 순회하며 필드 추가
        for cog_name in preferred_order:
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
                
            display_name = categories.get(cog_name, f"📦 {cog_name}")
            cmds = cog.get_app_commands()
            if not cmds:
                continue

            command_list = ""
            for cmd in cmds:
                # 설명이 너무 길면 자르기
                desc = (cmd.description[:40] + '..') if len(cmd.description) > 40 else cmd.description
                
                if cog_name in admin_categories:
                    command_list += f"`/{cmd.name}` - {desc} 🛡️`[관리자]`\n"
                else:
                    command_list += f"`/{cmd.name}` - {desc}\n"
            
            if command_list:
                embed.add_field(name=display_name, value=command_list, inline=False)

        # 4. 리스트에 없는 나머지 Cog가 있다면 마지막에 추가 (예외 방지)
        for name, cog in self.bot.cogs.items():
            if name not in preferred_order:
                cmds = cog.get_app_commands()
                if cmds:
                    display_name = categories.get(name, f"📦 {name}")
                    command_list = "\n".join([f"`/{c.name}` - {c.description}" for c in cmds])
                    embed.add_field(name=display_name, value=command_list, inline=False)

        # 하단 팁 및 안내
        embed.add_field(
            name="💡 팁", 
            value="`/출석`으로 매일 투자 지원금을 받을 수 있습니다! 잊지 말고 챙기세요.", 
            inline=False
        )
        
        if interaction.user.guild_permissions.administrator:
            embed.add_field(name="🛡️ 관리자 권한 확인됨", value="`[관리자]` 표시 명령어로 서버 설정을 관리하세요.", inline=False)
        else:
            embed.add_field(name="ℹ️ 안내", value="`[관리자]` 표시 명령어는 관리자 권한이 필요합니다.", inline=False)

        embed.set_footer(text=f"현재 {len(self.bot.guilds)}개의 서버에서 구렁이가 서식 중입니다.")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))