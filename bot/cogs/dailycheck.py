import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta

class DailyCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = os.getenv("DATABASE_PATH", "data/hawawa.db")
        self.update_database_schema()

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def update_database_schema(self):
        """DB 테이블 확인 및 연속 출석용 컬럼 자동 추가"""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        # 1. 테이블이 없는 경우를 대비해 기본 구조 생성 (stock.py와 동기화)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_wallets (
                user_id INTEGER PRIMARY KEY, 
                balance INTEGER DEFAULT 1000000
            )
        """)
        
        # 2. 현재 컬럼 목록 확인
        cur.execute("PRAGMA table_info(user_wallets)")
        columns = [column[1] for column in cur.fetchall()]
        
        # 'last_attendance' (마지막 출석일) 컬럼 추가
        if "last_attendance" not in columns:
            try:
                cur.execute("ALTER TABLE user_wallets ADD COLUMN last_attendance TEXT")
            except: pass
        
        # 'streak' (연속 출석 일수) 컬럼 추가
        if "streak" not in columns:
            try:
                cur.execute("ALTER TABLE user_wallets ADD COLUMN streak INTEGER DEFAULT 0")
                print("✅ [DailyCheck] 'streak' 컬럼이 DB에 추가되었습니다.")
            except: pass
            
        conn.commit()
        conn.close()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """설정된 출석 채널에서만 명령어가 작동하도록 제한"""
        config = self.bot.config_cache.get(interaction.guild.id, {})
        attendance_ch_id = config.get("attendance")

        if attendance_ch_id and interaction.channel_id != attendance_ch_id:
            attendance_ch = self.bot.get_channel(attendance_ch_id)
            ch_mention = attendance_ch.mention if attendance_ch else "지정된 채널"
            await interaction.response.send_message(
                f"❌ 출석체크는 {ch_mention} 채널에서만 가능합니다!", 
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="출석", description="매일 보상을 받습니다. 연속 출석 시 보너스가 추가됩니다!")
    async def daily_attendance(self, interaction: discord.Interaction):
        # DB 작업 전 응답 지연 (응답 없음 방지)
        await interaction.response.defer()
        
        user_id = interaction.user.id
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        base_reward = 5000      # 기본 보상금
        bonus_per_day = 1000    # 연속 1일당 추가금
        max_bonus = 5000        # 최대 보너스 한도
        
        conn = self.get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT last_attendance, balance, streak FROM user_wallets WHERE user_id = ?", (user_id,))
        user = cur.fetchone()

        if user is None:
            # 신규 유저: 기본금 100만 + 보상 5천
            initial_balance = 1000000 + base_reward
            cur.execute("INSERT INTO user_wallets (user_id, balance, last_attendance, streak) VALUES (?, ?, ?, ?)", 
                        (user_id, initial_balance, today, 1))
            msg = (f"🎊 **{interaction.user.display_name}**님, 첫 방문을 환영합니다!\n"
                   f"첫 출석 보상으로 **{base_reward:,}원**을 드렸습니다.\n"
                   f"(거래소 정착 지원금 포함 현재 잔고: **{initial_balance:,}원**)")
        else:
            last_date = user['last_attendance']
            current_streak = user['streak'] if user['streak'] is not None else 0

            if last_date == today:
                msg = "❌ 오늘은 이미 출석체크를 완료하셨습니다. 내일 다시 찾아주세요!"
            else:
                # 연속 출석 판정
                if last_date == yesterday:
                    new_streak = current_streak + 1
                else:
                    new_streak = 1 # 하루라도 거르면 1일차로 초기화
                
                # 보상 계산 (기본 5,000 + 보너스)
                streak_bonus = min((new_streak - 1) * bonus_per_day, max_bonus)
                total_reward = base_reward + streak_bonus
                
                current_balance = user['balance'] if user['balance'] is not None else 0
                new_balance = current_balance + total_reward
                
                cur.execute("UPDATE user_wallets SET balance = ?, last_attendance = ?, streak = ? WHERE user_id = ?", 
                            (new_balance, today, new_streak, user_id))
                
                streak_info = f" 🔥 **{new_streak}일 연속!**" if new_streak > 1 else ""
                bonus_info = f"\n(연속 보너스 **+{streak_bonus:,}원** 포함)" if streak_bonus > 0 else ""
                
                msg = (f"✅ 출석 완료! 보상으로 **{total_reward:,}원**을 받았습니다.{streak_info}"
                       f"{bonus_info}\n현재 잔고: **{new_balance:,}원**")

        conn.commit()
        conn.close()
        
        # defer()를 사용했으므로 followup으로 메시지 전송
        await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(DailyCheck(bot))