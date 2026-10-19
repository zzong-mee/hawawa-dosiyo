import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
from collections import deque
import asyncio

# 검색 결과 선택 메뉴 (기존과 동일)
class SongSelectView(discord.ui.View):
    def __init__(self, search_results, music_cog):
        super().__init__(timeout=30)
        self.search_results = search_results
        self.music_cog = music_cog
        self.selected_data = None

        options = []
        for i, res in enumerate(search_results):
            title = res.get('title', '제목 없음')[:90]
            options.append(discord.SelectOption(label=f"{i+1}. {title}", value=str(i)))

        self.select = discord.ui.Select(placeholder="재생할 곡을 선택하세요...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        idx = int(self.select.values[0])
        self.selected_data = self.search_results[idx]
        self.stop()
        await interaction.response.edit_message(content=f"✅ **{self.selected_data.get('title')}** 선택됨!", view=None)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        self.YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'default_search': 'ytsearch',
            'ignoreerrors': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }

    # --- [핵심 수정] 음악 채널 제한 로직 ---
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Cog 내의 모든 명령어가 실행되기 전 채널 설정을 확인합니다."""
        config = self.bot.config_cache.get(interaction.guild.id)
        
        # DB에 음악 채널이 설정되어 있는 경우
        if config and config.get("music"):
            if interaction.channel.id != config["music"]:
                music_channel = self.bot.get_channel(config["music"])
                channel_mention = music_channel.mention if music_channel else "음악 전용 채널"
                
                await interaction.response.send_message(
                    f"❌ 음악 명령어는 {channel_mention}에서만 사용할 수 있습니다!", 
                    ephemeral=True
                )
                return False
        return True

    def check_queue(self, interaction):
        guild_id = interaction.guild.id
        if guild_id in self.queues and self.queues[guild_id]:
            next_song = self.queues[guild_id].popleft()
            interaction.guild.voice_client.play(
                next_song['source'], 
                after=lambda e: self.check_queue(interaction)
            )
            self.bot.loop.create_task(
                interaction.channel.send(f"⏭️ 다음 곡 재생: **{next_song['title']}**")
            )

    @app_commands.command(name="재생", description="노래 제목이나 유튜브 링크를 입력하세요.")
    async def play(self, interaction: discord.Interaction, search: str):
        # 1. 보이스 채널 접속 여부만 체크 (채널 제한은 interaction_check가 수행함)
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)

        await interaction.response.defer()

        if "shorts/" in search:
            search = search.replace("shorts/", "watch?v=")

        try:
            ydl_opts = self.YDL_OPTIONS.copy()
            if not search.startswith("http"):
                ydl_opts['default_search'] = 'ytsearch5'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(search, download=False))
                
                if not info:
                    return await interaction.followup.send("❌ 결과를 찾을 수 없습니다.")

                if search.startswith("http"):
                    if 'entries' in info:
                        await interaction.followup.send("📂 재생목록을 대기열에 추가합니다...")
                        for entry in info['entries']:
                            if entry: await self.add_to_queue(interaction, entry['url'], entry['title'])
                    else:
                        await interaction.followup.send(f"🎵 **{info['title']}** 분석 중...")
                        await self.add_to_queue(interaction, info['webpage_url'], info['title'])
                
                else:
                    results = info.get('entries', [])
                    if not results:
                        return await interaction.followup.send("❌ 검색 결과가 없습니다.")
                    
                    view = SongSelectView(results[:5], self)
                    msg = await interaction.followup.send("🔎 검색 결과입니다. 아래에서 선택하세요:", view=view)
                    
                    await view.wait()
                    
                    if view.selected_data:
                        target_url = view.selected_data.get('url') or view.selected_data.get('webpage_url')
                        await self.add_to_queue(interaction, target_url, view.selected_data['title'])
                    else:
                        await msg.edit(content="❌ 선택 시간이 초과되어 취소되었습니다.", view=None)

        except Exception as e:
            if not interaction.has_responded():
                await interaction.followup.send(f"❌ 오류 발생: {str(e)[:50]}")
            else:
                await interaction.channel.send(f"❌ 실행 중 오류: {str(e)[:50]}")

    async def add_to_queue(self, interaction, url, title):
        guild_id = interaction.guild.id
        try:
            def get_real_url():
                with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                    return ydl.extract_info(url, download=False)['url']
            
            real_url = await self.bot.loop.run_in_executor(None, get_real_url)
            source = await discord.FFmpegOpusAudio.from_probe(real_url, **self.FFMPEG_OPTIONS)

            if not interaction.guild.voice_client:
                await interaction.user.voice.channel.connect()

            vc = interaction.guild.voice_client
            if vc.is_playing():
                if guild_id not in self.queues: self.queues[guild_id] = deque()
                self.queues[guild_id].append({'source': source, 'title': title})
                await interaction.channel.send(f"📝 대기열 추가: **{title}**")
            else:
                vc.play(source, after=lambda e: self.check_queue(interaction))
                await interaction.channel.send(f"🎵 지금 재생: **{title}**")
        except Exception as e:
            print(f"Queue Error: {e}")

    @app_commands.command(name="스킵", description="현재 곡을 건너뜜")
    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ 현재 곡을 스킵했습니다.")
        else:
            await interaction.response.send_message("❌ 재생 중인 곡이 없습니다.", ephemeral=True)

    @app_commands.command(name="대기열", description="현재 재생 목록 확인")
    async def queue(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id not in self.queues or not self.queues[guild_id]:
            return await interaction.response.send_message("📋 대기열이 비어 있습니다.")

        queue_list = list(self.queues[guild_id])
        msg = "📋 **현재 대기열 (최대 10곡)**\n"
        for i, song in enumerate(queue_list[:10]):
            msg += f"{i+1}. {song['title']}\n"
        await interaction.response.send_message(msg)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id: return
        vc = member.guild.voice_client
        if not vc: return
        
        if before.channel and before.channel.id == vc.channel.id:
            remaining = [m for m in vc.channel.members if not m.bot]
            if len(remaining) == 0:
                if member.guild.id in self.queues: self.queues[member.guild.id].clear()
                await vc.disconnect()
                
                # [수정] 설정된 음악 채널로 퇴장 알림 전송
                config = self.bot.config_cache.get(member.guild.id)
                if config and config.get("music"):
                    chan = self.bot.get_channel(config["music"])
                    if chan: await chan.send("🔇 모든 유저가 퇴장하여 방송을 종료합니다.")

async def setup(bot):
    await bot.add_cog(Music(bot))