import discord
from discord.ext import commands
import datetime

class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_log(self, guild, embed):
        """settings.py에서 관리하는 캐시를 참조하여 로그를 전송합니다."""
        if not guild: return
        
        # settings.py에서 저장한 config_cache에서 log 채널 ID를 가져옴
        config = self.bot.config_cache.get(guild.id)
        if config and config.get("log"):
            channel = self.bot.get_channel(config["log"])
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass 

    # --- [이벤트] 메시지 삭제 ---
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        
        embed = discord.Embed(
            title="🗑️ 메시지 삭제됨",
            description=f"**채널**: {message.channel.mention}\n**작성자**: {message.author.mention}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        content = (message.content[:1000] + '...') if len(message.content) > 1000 else message.content
        embed.add_field(name="삭제된 내용", value=content or "내용 없음 (이미지/파일 등)", inline=False)
        await self.send_log(message.guild, embed)

    # --- [이벤트] 메시지 수정 ---
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content or not before.guild: return
        
        embed = discord.Embed(
            title="📝 메시지 수정됨",
            description=f"**채널**: {before.channel.mention}\n**작성자**: {before.author.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="수정 전", value=before.content or "내용 없음", inline=False)
        embed.add_field(name="수정 후", value=after.content or "내용 없음", inline=False)
        await self.send_log(before.guild, embed)

    # --- [이벤트] 음성 채널 활동 ---
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild: return

        embed = discord.Embed(color=discord.Color.light_grey(), timestamp=datetime.datetime.now())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

        if before.channel is None and after.channel is not None:
            embed.title = "🔊 음성 채널 입장"
            embed.description = f"{member.mention} 님이 {after.channel.mention} 방에 들어왔습니다."
            embed.color = discord.Color.green()
        elif before.channel is not None and after.channel is None:
            embed.title = "🔇 음성 채널 퇴장"
            embed.description = f"{member.mention} 님이 {before.channel.mention} 방에서 나갔습니다."
            embed.color = discord.Color.orange()
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            embed.title = "🔄 음성 채널 이동"
            embed.description = f"{member.mention} 님이 이동함\n**이전**: {before.channel.mention}\n**이후**: {after.channel.mention}"
            embed.color = discord.Color.blue()
        else:
            return 

        await self.send_log(member.guild, embed)

async def setup(bot):
    await bot.add_cog(Logs(bot))