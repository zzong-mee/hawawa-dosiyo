import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot.cogs.reminders import Reminders
from bot.cogs.role_panels import RolePanel, RolePanels
from bot.storage import Store


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.db')
        self.user = SimpleNamespace(send=AsyncMock())
        self.bot = SimpleNamespace(fetch_user=AsyncMock(return_value=self.user))

    async def asyncTearDown(self):
        self.temp.cleanup()

    def interaction(self, guild=1, user=10, message=100):
        return SimpleNamespace(
            guild_id=guild, guild=SimpleNamespace(id=guild),
            user=SimpleNamespace(id=user), message=SimpleNamespace(id=message),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_reminder_restarts_and_sends_once(self):
        cog = Reminders(self.bot, self.store)
        interaction = self.interaction()
        with patch('bot.cogs.reminders.time.time', return_value=100):
            await cog.create_timer.callback(cog, interaction, name='hello', text='hello', timer=1)
        restarted = Reminders(self.bot, Store(self.store.path))
        await restarted.deliver_once(159)
        self.user.send.assert_not_awaited()
        await restarted.deliver_once(160)
        self.user.send.assert_awaited_once()
        await restarted.deliver_once(200)
        self.user.send.assert_awaited_once()
        self.assertEqual(await self.store.execute('SELECT * FROM reminders'), [])

    async def test_reminder_cancellation_is_owner_and_guild_scoped(self):
        rows = await self.store.execute("INSERT INTO reminders (guild,user,text,due,name) VALUES (1,10,'hello',1,'hello') RETURNING id")
        identifier = rows[0][0]
        cog = Reminders(self.bot, self.store)
        for interaction in (self.interaction(user=20), self.interaction(guild=2)):
            await cog.delete.callback(cog, interaction, name='hello')
            self.assertEqual(len(await self.store.execute('SELECT * FROM reminders')), 1)
        await cog.delete.callback(cog, self.interaction(), name='hello')
        self.assertEqual(await self.store.execute('SELECT * FROM reminders'), [])

    async def test_reminder_limit_is_global_per_user(self):
        cog = Reminders(self.bot, self.store)
        for _ in range(26):
            await cog.create_timer.callback(cog, self.interaction(), name=f'hello-{_}', text='hello', timer=1)
        self.assertEqual((await self.store.execute('SELECT COUNT(*) FROM reminders'))[0][0], 25)

    async def test_forbidden_dm_marks_failed_and_stale_lease_recovers(self):
        await self.store.execute("INSERT INTO reminders (guild,user,text,due,state) VALUES (1,10,'hello',100,'sending')")
        self.user.send.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'blocked')
        await Reminders(self.bot, self.store).deliver_once(100)
        self.assertEqual((await self.store.execute('SELECT state FROM reminders'))[0][0], 'failed')

    async def test_role_panel_survives_recreation_and_toggles(self):
        await self.store.execute('INSERT INTO role_panels (guild,message,role) VALUES (1,100,30)')
        view = RolePanel(Store(self.store.path))
        self.assertTrue(view.is_persistent())
        member = SimpleNamespace(roles=[], add_roles=AsyncMock(), remove_roles=AsyncMock())
        role = object()
        interaction = self.interaction()
        interaction.guild.get_role = lambda identifier: role
        interaction.guild.fetch_member = AsyncMock(return_value=member)
        with patch.dict(RolePanel.toggle.__globals__, {'safe_role': lambda guild, role: True}):
            await view.children[0].callback(interaction)
            member.add_roles.assert_awaited_once()
            member.roles = [role]
            await view.children[0].callback(interaction)
            member.remove_roles.assert_awaited_once()
        view.stop()

    async def test_role_panel_different_message_guild_and_disabled_are_denied(self):
        await self.store.execute('INSERT INTO role_panels (guild,message,role) VALUES (1,100,30)')
        view = RolePanel(self.store)
        for guild, message in ((2, 100), (1, 101)):
            interaction = self.interaction(guild=guild, message=message)
            interaction.guild.get_role = lambda identifier: object()
            interaction.guild.fetch_member = AsyncMock()
            await view.children[0].callback(interaction)
            interaction.guild.fetch_member.assert_not_awaited()
        cog = RolePanels(self.bot, self.store)
        await cog.disable.callback(cog, self.interaction(), '100')
        self.assertEqual((await self.store.execute('SELECT enabled FROM role_panels'))[0][0], 0)
        view.stop()


if __name__ == '__main__':
    unittest.main()
