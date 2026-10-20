import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from bot.cogs.giveaways import Giveaways, GiveawayView
from bot.cogs.starboard import Starboard
from bot.cogs.temporary_roles import TemporaryRoles
from bot.storage import Store


class EngagementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'new.db')

    async def asyncTearDown(self):
        self.temp.cleanup()

    def interaction(self, guild=1, user=10, message=100):
        return SimpleNamespace(
            guild=SimpleNamespace(id=guild), user=SimpleNamespace(id=user, bot=False), message=SimpleNamespace(id=message),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_temporary_role_expiry_after_restart_is_idempotent(self):
        role = object()
        member = SimpleNamespace(roles=[role], remove_roles=AsyncMock())
        guild = SimpleNamespace(get_role=lambda identifier: role, fetch_member=AsyncMock(return_value=member))
        bot = SimpleNamespace(get_guild=lambda identifier: guild)
        await self.store.execute('INSERT INTO temporary_roles VALUES (1,10,30,100)')
        cog = TemporaryRoles(bot, Store(self.store.path))
        await cog.expire_once(99)
        member.remove_roles.assert_not_awaited()
        await cog.expire_once(100)
        member.remove_roles.assert_awaited_once()
        await cog.expire_once(101)
        member.remove_roles.assert_awaited_once()
        self.assertEqual(await self.store.execute('SELECT * FROM temporary_roles'), [])

    async def test_temporary_role_failure_keeps_schedule(self):
        role = object()
        member = SimpleNamespace(roles=[role], remove_roles=AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'denied')))
        guild = SimpleNamespace(get_role=lambda identifier: role, fetch_member=AsyncMock(return_value=member))
        bot = SimpleNamespace(get_guild=lambda identifier: guild)
        await self.store.execute('INSERT INTO temporary_roles VALUES (1,10,30,100)')
        await TemporaryRoles(bot, self.store).expire_once(100)
        self.assertEqual((await self.store.execute('SELECT due FROM temporary_roles'))[0][0], 160)

    async def test_giveaway_entries_restart_uniqueness_and_guild_isolation(self):
        await self.store.execute("INSERT INTO giveaways (guild,message,channel,prize,due,count) VALUES (1,100,20,'Prize',9999999999,1)")
        cog = Giveaways(SimpleNamespace(), Store(self.store.path))
        view = GiveawayView(cog)
        self.assertTrue(view.is_persistent())
        await view.update_entry(self.interaction(), True)
        await view.update_entry(self.interaction(), True)
        await view.update_entry(self.interaction(guild=2), True)
        self.assertEqual(await self.store.execute('SELECT user FROM giveaway_entries'), [(10,)])
        await view.update_entry(self.interaction(), False)
        self.assertEqual(await self.store.execute('SELECT * FROM giveaway_entries'), [])
        view.stop()

    async def test_giveaway_result_frozen_and_announcement_retried_without_reroll(self):
        await self.store.execute("INSERT INTO giveaways (guild,message,channel,prize,due,count) VALUES (1,100,20,'Prize',100,2)")
        for user in (10, 20, 30):
            await self.store.execute('INSERT INTO giveaway_entries VALUES (1,100,?)', (user,))
        channel = Mock(spec=discord.TextChannel)
        edit = AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'denied'))
        channel.get_partial_message.return_value = SimpleNamespace(edit=edit)
        guild = SimpleNamespace(get_channel=lambda identifier: channel)
        bot = SimpleNamespace(get_guild=lambda identifier: guild)
        await Giveaways(bot, self.store).finish_once(100)
        result = (await self.store.execute('SELECT result FROM giveaways'))[0][0]
        self.assertEqual(len(set(json.loads(result))), 2)
        edit.side_effect = None
        await Giveaways(bot, Store(self.store.path)).finish_once(101)
        self.assertEqual((await self.store.execute('SELECT result,announced FROM giveaways'))[0], (result, 1))
        self.assertEqual(len(await self.store.execute('SELECT * FROM giveaway_entries')), 3)
        edit.reset_mock()
        await Giveaways(bot, self.store).finish_once(102)
        edit.assert_not_awaited()

    async def test_starboard_public_only_and_single_post(self):
        source = Mock(spec=discord.TextChannel)
        destination = Mock(spec=discord.TextChannel)
        destination.id = 20
        source.permissions_for.return_value = discord.Permissions(view_channel=False)
        message = SimpleNamespace(id=100, author=SimpleNamespace(bot=False), reactions=[SimpleNamespace(emoji='⭐', count=3)], jump_url='https://discord.com/channels/1/10/100')
        source.fetch_message = AsyncMock(return_value=message)
        destination.send = AsyncMock(return_value=SimpleNamespace(id=200))
        edit = AsyncMock()
        destination.get_partial_message.return_value = SimpleNamespace(edit=edit)
        guild = SimpleNamespace(id=1, default_role=object(), get_channel=lambda identifier: source if identifier == 10 else destination)
        bot = SimpleNamespace(get_guild=lambda identifier: guild)
        await self.store.set(1, 'starboard', '20')
        cog = Starboard(bot, self.store)
        payload = SimpleNamespace(guild_id=1, channel_id=10, message_id=100, emoji='⭐')
        await cog.update(payload)
        source.fetch_message.assert_not_awaited()
        source.permissions_for.return_value = discord.Permissions(view_channel=True)
        await cog.update(payload)
        destination.send.assert_awaited_once()
        await Starboard(bot, Store(self.store.path)).update(payload)
        destination.send.assert_awaited_once()
        edit.assert_awaited_once()

    async def test_new_configuration_commands_have_permission_checks(self):
        interaction = SimpleNamespace(permissions=discord.Permissions())
        for cog, name in ((TemporaryRoles(None), 'temprole'), (Giveaways(None), 'giveaway'), (Starboard(None), 'starboard')):
            for check in getattr(cog, name).checks:
                with self.assertRaises(discord.app_commands.MissingPermissions):
                    await check(interaction)


if __name__ == '__main__':
    unittest.main()
