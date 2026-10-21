"""Persistent personal reminders delivered through Discord DMs."""
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
import discord
from discord import app_commands
from discord.ext import commands, tasks
from bot.storage import Store
logger = logging.getLogger("hawawa.reminders")
KST = ZoneInfo("Asia/Seoul")

class Reminders(commands.Cog):
    reminder = app_commands.Group(name="reminder", description="개인 DM 리마인더를 관리합니다.")
    create_group = app_commands.Group(name="create", description="리마인더 방식을 선택해 생성합니다.", parent=reminder)
    def __init__(self, bot, store=None):
        self.bot, self.store = bot, store or Store()
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.deliver.is_running(): self.deliver.start()
    def cog_unload(self): self.deliver.cancel()

    async def _create(self, interaction, name, text, due, repeat_minutes=None, schedule=""):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild, user = interaction.guild_id or 0, interaction.user.id
        rows = await self.store.execute("INSERT INTO reminders (guild,user,text,due,name) SELECT ?,?,?,?,? WHERE (SELECT COUNT(*) FROM reminders WHERE user=? AND state IN ('pending','sending')) < 25 RETURNING id", (guild, user, text.strip(), due, name.strip(), user))
        message = f"[{name.strip()}] 리마인더를 {schedule}에 DM으로 보냅니다. 서버 멤버의 DM을 허용해주세요." if rows else "진행 중인 리마인더는 사용자당 최대 25개입니다."
        if rows and repeat_minutes is not None:
            await self.store.execute("INSERT INTO reminder_repeats VALUES (?,?)", (rows[0][0], repeat_minutes)); message += f" 이후 {repeat_minutes}분마다 반복합니다."
        await interaction.followup.send(message, ephemeral=True)

    @create_group.command(name="alert", description="한국 시간에 맞춰 리마인더를 생성합니다.")
    @app_commands.describe(name="알림 이름", text="알림 문구", alert="한국 시간 HH:MM", repeat_minutes="반복 간격 (선택)")
    async def create_alert(self, interaction, name: app_commands.Range[str, 1, 80], text: app_commands.Range[str, 1, 1500], alert: str, repeat_minutes: app_commands.Range[int, 1, 43200] | None = None):
        match = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", alert.strip())
        if not match:
            await interaction.response.send_message("알림은 한국 시간 기준 HH:MM 형식으로 입력해주세요. 예: 09:30", ephemeral=True); return
        now_kst = datetime.now(KST); target = now_kst.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        if target <= now_kst: target += timedelta(days=1)
        await self._create(interaction, name, text, target.astimezone(timezone.utc).timestamp(), repeat_minutes, f"한국 시간 {alert.strip()}")

    @create_group.command(name="timer", description="몇 분 후 리마인더를 생성합니다.")
    @app_commands.describe(name="알림 이름", text="알림 문구", timer="몇 분 후 알림")
    async def create_timer(self, interaction, name: app_commands.Range[str, 1, 80], text: app_commands.Range[str, 1, 1500], timer: app_commands.Range[int, 1, 43200]):
        await self._create(interaction, name, text, time.time() + timer * 60, schedule=f"<t:{int(time.time() + timer * 60)}:R>")

    @reminder.command(name="list", description="내 리마인더 목록을 확인합니다.")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        rows = await self.store.execute("SELECT r.name,r.due,r.state,rr.minutes FROM reminders r LEFT JOIN reminder_repeats rr ON rr.reminder=r.id WHERE r.guild=? AND r.user=? AND r.state IN ('pending','sending','failed') ORDER BY r.due LIMIT 25", (interaction.guild_id or 0, interaction.user.id))
        message = "\n".join(f"[{name}] · <t:{int(due)}:f> · {state}{f' · {repeat}분마다 반복' if repeat else ''}" for name, due, state, repeat in rows) or "이 서버에서 만든 리마인더가 없습니다."
        await interaction.followup.send(message, ephemeral=True)

    @reminder.command(name="delete", description="이름으로 내 리마인더를 삭제합니다.")
    @app_commands.describe(name="삭제할 알림 이름")
    async def delete(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 80]):
        await interaction.response.defer(ephemeral=True, thinking=True); guild, user = interaction.guild_id or 0, interaction.user.id
        rows = await self.store.execute("DELETE FROM reminders WHERE id=(SELECT id FROM reminders WHERE guild=? AND user=? AND name=? ORDER BY id DESC LIMIT 1) RETURNING id", (guild, user, name.strip()))
        if rows: await self.store.execute("DELETE FROM reminder_repeats WHERE reminder=?", (rows[0][0],))
        await interaction.followup.send("알림을 삭제했습니다." if rows else "삭제할 수 없습니다. 이름과 서버를 확인해주세요.", ephemeral=True)

    async def deliver_once(self, now=None):
        now = time.time() if now is None else now
        rows = await self.store.execute("UPDATE reminders SET state='sending', due=?, attempts=attempts+1 WHERE id IN (SELECT id FROM reminders WHERE (state='pending' AND due<=?) OR (state='sending' AND due<=?) ORDER BY due LIMIT 10) RETURNING id,user,text,name,attempts", (now + 300, now, now))
        for identifier, user_id, text, name, attempts in rows:
            try:
                user = await self.bot.fetch_user(user_id); label = f" · {name}" if name else ""
                await user.send(f"⏰ 리마인더{label}\n{text}", allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.NotFound): await self.store.execute("UPDATE reminders SET state='failed' WHERE id=?", (identifier,))
            except discord.HTTPException: await self.store.execute("UPDATE reminders SET state=?,due=? WHERE id=?", ('failed' if attempts >= 3 else 'pending', now + 60, identifier))
            else:
                repeats = await self.store.execute("SELECT minutes FROM reminder_repeats WHERE reminder=?", (identifier,))
                if repeats: await self.store.execute("UPDATE reminders SET state='pending',attempts=0,due=? WHERE id=?", (now + repeats[0][0] * 60, identifier))
                else: await self.store.execute("DELETE FROM reminders WHERE id=?", (identifier,))
        await self.store.execute("DELETE FROM reminders WHERE state='failed' AND due<?", (now - 7 * 86400,)); await self.store.execute("DELETE FROM reminder_repeats WHERE reminder NOT IN (SELECT id FROM reminders)")

    @tasks.loop(seconds=15)
    async def deliver(self):
        try: await self.deliver_once()
        except Exception: logger.exception("Reminder delivery iteration failed")
    async def cog_app_command_error(self, interaction, error):
        logger.error("Reminder command failed: %s", type(error).__name__); text = "리마인더 처리에 실패했습니다. 잠시 후 다시 시도해주세요."
        if interaction.response.is_done(): await interaction.followup.send(text, ephemeral=True)
        else: await interaction.response.send_message(text, ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(Reminders(bot))
