import discord
from discord.ext import commands
import re

class BigEmoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 메시지 '전체'가 이모티콘 하나로만 구성되었는지 엄격하게 검사 (^...$)
        self.emoji_pattern = re.compile(r"^<(a?):(\w+):(\d+)>$")

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. 봇이 보낸 메시지는 무시
        if message.author.bot:
            return

        # 2. 메시지 양옆 공백 제거 후 패턴 확인
        content = message.content.strip()
        match = self.emoji_pattern.match(content)

        # 3. 정확히 하나만 매칭될 때만 실행
        if match:
            animated = match.group(1) == "a"
            emoji_id = match.group(3)
            
            ext = "gif" if animated else "png"
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=512"

            embed = discord.Embed(color=message.author.color)
            embed.set_author(
                name=f"{message.author.display_name}", 
                icon_url=message.author.display_avatar.url
            )
            embed.set_image(url=emoji_url)
            
            # 확대된 이미지 전송
            await message.channel.send(embed=embed)

            # 원본 메시지 삭제
            try:
                await message.delete()
            except:
                pass

async def setup(bot):
    await bot.add_cog(BigEmoji(bot))