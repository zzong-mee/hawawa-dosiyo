"""Persistent personal reminders delivered through Discord DMs."""

import logging
import time
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.storage import Store

logger = logging.getLogger("hawawa.reminders")


class Reminders(commands.Cog):
    def __init__(self, bot, store=None):
        self.bot = bot
        self.store = store or Store()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.deliver.is_running():
            self.deliver.start()

    def cog_unload(self):
        self.deliver.cancel()

    @app_commands.command(name="reminder", description="개인 DM 리마인더를 생성·조회·취소합니다.")
    @app_commands.describe(action="create: 생성, list: 목록, cancel: 취소", minutes="몇 분 후 알림 (1분~30일)", text="알림 내용", reminder_id="취소할 리마인더 번호", repeat_minutes="반복 간격 (생략하면 일회성, 1분~30일)")
    async def reminder(
        self, interaction: discord.Interaction,
        action: Literal["create", "list", "cancel"],
        minutes: app_commands.Range[int, 1, 43200] | None = None,
        text: app_commands.Range[str, 1, 1500] | None = None,
        reminder_id: int | None = None,
        repeat_minutes: app_commands.Range[int, 1, 43200] | None = None,
    ):
        if action == "create" and (minutes is None or not text or not text.strip()):
            await interaction.response.send_message("minutes와 text를 입력해주세요.", ephemeral=True)
            return
        if action == "cancel" and reminder_id is None:
            await interaction.response.send_message("취소할 reminder_id를 입력해주세요.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild_id or 0
        user = interaction.user.id
        if action == "create":
            due = time.time() + minutes * 60
            rows = await self.store.execute(
                "INSERT INTO reminders (guild,user,text,due) SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM reminders WHERE user=? AND state IN ('pending','sending')) < 25 RETURNING id",
                (guild, user, text.strip(), due, user),
            )
            message = f"#{rows[0][0]} 리마인더를 <t:{int(due)}:R> DM으로 보냅니다. 서버 멤버의 DM을 허용해주세요." if rows else "진행 중인 리마인더는 사용자당 최대 25개입니다."
            if rows and repeat_minutes is not None:
                await self.store.execute("INSERT INTO reminder_repeats VALUES (?,?)", (rows[0][0], repeat_minutes))
                message += f" 이후 {repeat_minutes}분마다 반복합니다."
        elif action == "list":
            rows = await self.store.execute(
                "SELECT id,due,state FROM reminders WHERE guild=? AND user=? AND state IN ('pending','sending','failed') ORDER BY due LIMIT 25", (guild, user))
            message = "\n".join(f"#{identifier} · <t:{int(due)}:f> · {state}" for identifier, due, state in rows) or "이 서버에서 만든 리마인더가 없습니다."
        else:
            rows = await self.store.execute(
                "DELETE FROM reminders WHERE id=? AND guild=? AND user=? AND state IN ('pending','failed') RETURNING id", (reminder_id, guild, user))
            message = "취소했습니다." if rows else "취소할 수 없습니다. 번호·서버를 확인해주세요. 전송 중인 알림은 취소할 수 없습니다."
        await interaction.followup.send(message, ephemeral=True)

    async def deliver_once(self, now=None):
        now = time.time() if now is None else now
        # Reclaim abandoned deliveries after a crash. Delivery is at least once:
        # a crash after DM send but before deletion can cause a duplicate.
        rows = await self.store.execute(
            "UPDATE reminders SET state='sending', due=?, attempts=attempts+1 WHERE id IN (SELECT id FROM reminders WHERE (state='pending' AND due<=?) OR (state='sending' AND due<=?) ORDER BY due LIMIT 10) RETURNING id,user,text,attempts",
            (now + 300, now, now),
        )
        for identifier, user_id, text, attempts in rows:
            try:
                user = await self.bot.fetch_user(user_id)
                await user.send(f"⏰ 리마인더 #{identifier}\n{text}", allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.NotFound):
                await self.store.execute("UPDATE reminders SET state='failed' WHERE id=?", (identifier,))
            except discord.HTTPException:
                await self.store.execute("UPDATE reminders SET state=?,due=? WHERE id=?", ('failed' if attempts >= 3 else 'pending', now + 60, identifier))
            else:
                repeats = await self.store.execute("SELECT minutes FROM reminder_repeats WHERE reminder=?", (identifier,))
                if repeats:
                    await self.store.execute("UPDATE reminders SET state='pending',attempts=0,due=? WHERE id=?", (now + repeats[0][0] * 60, identifier))
                else:
                    await self.store.execute("DELETE FROM reminders WHERE id=?", (identifier,))
        # Failed reminders are visible for seven days, then their text is removed.
        await self.store.execute("DELETE FROM reminders WHERE state='failed' AND due<?", (now - 7 * 86400,))
        await self.store.execute("DELETE FROM reminder_repeats WHERE reminder NOT IN (SELECT id FROM reminders)")

    @tasks.loop(seconds=15)
    async def deliver(self):
        try:
            await self.deliver_once()
        except Exception:
            logger.exception("Reminder delivery iteration failed")

    async def cog_app_command_error(self, interaction, error):
        logger.error("Reminder command failed: %s", type(error).__name__)
        text = "리마인더 처리에 실패했습니다. 잠시 후 다시 시도해주세요."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminders(bot))
