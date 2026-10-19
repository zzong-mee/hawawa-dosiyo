import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

class ServerSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "data/hawawa.db")
        self.bot.config_cache = {}
        self.init_db()
        self.load_config()

    def init_db(self):
        """DB 테이블 생성 및 마이그레이션 (출석 채널 포함)"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS server_config (
                server_id INTEGER PRIMARY KEY,
                news_channel_id INTEGER,
                log_channel_id INTEGER,
                bot_channel_id INTEGER,
                music_channel_id INTEGER,
                attendance_channel_id INTEGER
            )
        """)
        
        # 부족한 컬럼 자동 추가
        required_columns = [
            ("news_channel_id", "INTEGER"),
            ("log_channel_id", "INTEGER"),
            ("bot_channel_id", "INTEGER"),
            ("music_channel_id", "INTEGER"),
            ("attendance_channel_id", "INTEGER")
        ]
        
        for col_name, col_type in required_columns:
            try:
                cur.execute(f"ALTER TABLE server_config ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
            
        conn.commit()
        conn.close()

    def load_config(self):
        """DB 설정값을 캐시에 로드"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM server_config")
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            keys = row.keys()
            self.bot.config_cache[row['server_id']] = {
                "news": row['news_channel_id'] if 'news_channel_id' in keys else None,
                "log": row['log_channel_id'] if 'log_channel_id' in keys else None,
                "stock": row['bot_channel_id'] if 'bot_channel_id' in keys else None,
                "music": row['music_channel_id'] if 'music_channel_id' in keys else None,
                "attendance": row['attendance_channel_id'] if 'attendance_channel_id' in keys else None
            }
        print(f"✅ [Settings] {len(self.bot.config_cache)}개 서버 설정 로드 완료")

    async def save_to_db(self, guild_id, column, channel_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO server_config (server_id, {column}) 
            VALUES (?, ?) 
            ON CONFLICT(server_id) DO UPDATE SET {column} = EXCLUDED.{column}
        """, (guild_id, channel_id))
        conn.commit()
        conn.close()

        # 캐시 업데이트 로직
        if guild_id not in self.bot.config_cache:
            self.bot.config_cache[guild_id] = {"news": None, "log": None, "stock": None, "music": None, "attendance": None}
        
        mapping = {
            "news_channel_id": "news", 
            "log_channel_id": "log", 
            "bot_channel_id": "stock",
            "music_channel_id": "music",
            "attendance_channel_id": "attendance"
        }
        self.bot.config_cache[guild_id][mapping[column]] = channel_id

    # --- 설정 명령어들 ---

    @app_commands.command(name="뉴스채널설정", description="뉴스 송출 채널 설정 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_news(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        await self.save_to_db(interaction.guild.id, "news_channel_id", 채널.id)
        await interaction.response.send_message(f"📢 뉴스 채널이 {채널.mention}으로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="로그채널설정", description="로그 기록 채널 설정 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        await self.save_to_db(interaction.guild.id, "log_channel_id", 채널.id)
        await interaction.response.send_message(f"📜 로그 채널이 {채널.mention}으로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="주식채널설정", description="주식 명령어 전용 채널 설정 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_stock(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        await self.save_to_db(interaction.guild.id, "bot_channel_id", 채널.id)
        await interaction.response.send_message(f"📈 주식 전용 채널이 {채널.mention}으로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="음악채널설정", description="음악 전용 채널 설정 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_music(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        await self.save_to_db(interaction.guild.id, "music_channel_id", 채널.id)
        await interaction.response.send_message(f"🎵 음악 채널이 {채널.mention}으로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="출석채널설정", description="출석체크 전용 채널 설정 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_attendance(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        await self.save_to_db(interaction.guild.id, "attendance_channel_id", 채널.id)
        await interaction.response.send_message(f"📅 출석 전용 채널이 {채널.mention}으로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="채널설정모음", description="현재 서버의 모든 전용 채널 현황 확인")
    async def show_all_settings(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        config = self.bot.config_cache.get(guild_id, {})

        def get_ch_mention(ch_id):
            if not ch_id: return "❌ 미설정"
            channel = self.bot.get_channel(ch_id)
            return channel.mention if channel else "⚠️ 채널 찾을 수 없음"

        embed = discord.Embed(title=f"🏢 {interaction.guild.name} 설정 현황", color=discord.Color.blue())
        embed.add_field(name="📰 뉴스", value=get_ch_mention(config.get("news")), inline=True)
        embed.add_field(name="📜 로그", value=get_ch_mention(config.get("log")), inline=True)
        embed.add_field(name="📈 주식", value=get_ch_mention(config.get("stock")), inline=True)
        embed.add_field(name="🎵 음악", value=get_ch_mention(config.get("music")), inline=True)
        embed.add_field(name="📅 출석", value=get_ch_mention(config.get("attendance")), inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerSettings(bot))