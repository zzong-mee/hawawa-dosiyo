import discord
from discord import app_commands
from discord.ext import commands
import asyncio

class Clear(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="청소", description="채팅방의 메시지를 지정한 개수만큼 삭제합니다.")
    @app_commands.describe(개수="삭제할 메시지 수 (1~100)")
    # 관리자 권한이 있는 사람만 사용 가능하도록 설정
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_chat(self, interaction: discord.Interaction, 개수: int):
        # 1. 숫자 범위 체크
        if 개수 < 1 or 개수 > 100:
            return await interaction.response.send_message("❌ 1개에서 100개 사이의 숫자만 입력해 주세요.", ephemeral=True)

        # 2. 답변 지연 (메시지 삭제 작업은 시간이 걸릴 수 있음)
        await interaction.response.defer(ephemeral=True)

        try:
            # 3. 메시지 삭제 실행 (purge)
            # 최근 메시지부터 지정된 개수만큼 삭제합니다.
            deleted = await interaction.channel.purge(limit=개수)
            
            # 4. 결과 보고 (명령어를 친 사람에게만 보임)
            await interaction.followup.send(f"✅ 성공적으로 **{len(deleted)}개**의 메시지를 청소했습니다!")
            
        except discord.Forbidden:
            await interaction.followup.send("❌ 제게 '관리자' 권한이 없어서 삭제할 수 없어요.")
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: {e}")

    # 권한이 없는 유저가 사용했을 때 에러 처리
    @clear_chat.error
    async def clear_chat_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("🚫 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Clear(bot))