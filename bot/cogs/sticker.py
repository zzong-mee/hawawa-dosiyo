import discord
from discord.ext import commands

class StickerExpander(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. 봇이 보낸 메시지 무시
        if message.author.bot:
            return

        # 2. 메시지에 스티커가 있는지 확인
        if message.stickers:
            sticker = message.stickers[0]
            
            # 3. 임베드 생성
            embed = discord.Embed(color=discord.Color.blue())
            
            # 유저 프사 URL 가져오기 (가장 안전한 방식)
            user_avatar = message.author.display_avatar.url
            
            # 상단 유저 정보 표시
            embed.set_author(
                name=message.author.display_name, 
                icon_url=user_avatar
            )

            # 4. 스티커 이미지 설정 (Lottie 형식인 경우 대비)
            # 만약 애니메이션 스티커(Lottie)라면 URL이 이미지가 아닐 수 있습니다.
            embed.set_image(url=sticker.url)

            # 5. 원본 삭제 및 전송
            try:
                # 봇에게 '메시지 관리' 권한이 있을 때만 삭제 시도
                if message.guild and message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()
                
                await message.channel.send(embed=embed)
            except Exception as e:
                # 삭제에 실패하더라도 이미지는 보냄
                await message.channel.send(embed=embed)
                print(f"스티커 처리 오류: {e}")

async def setup(bot):
    await bot.add_cog(StickerExpander(bot))