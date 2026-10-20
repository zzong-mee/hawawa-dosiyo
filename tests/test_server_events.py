import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot.cogs.server_events import ServerEvents
from bot.storage import Store


class ServerEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'events.db')
        self.cog = ServerEvents(SimpleNamespace(), self.store)

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def test_experience_opt_in_cooldown_bots_and_server_isolation(self):
        message = SimpleNamespace(guild=SimpleNamespace(id=1), author=SimpleNamespace(id=10, bot=False), webhook_id=None)
        await self.cog.on_message(message)
        self.assertEqual(await self.store.execute('SELECT * FROM experience'), [])
        await self.store.set(1, 'levels', 'on')
        for now in (100, 110, 160):
            with patch('bot.cogs.server_events.time.time', return_value=now):
                await self.cog.on_message(message)
        self.assertEqual((await self.store.execute('SELECT xp FROM experience WHERE guild=1'))[0][0], 20)
        message.guild.id = 2
        await self.cog.on_message(message)
        self.assertEqual(await self.store.execute('SELECT xp FROM experience WHERE guild=2'), [])
        message.guild.id = 1
        message.author.bot = True
        await self.cog.on_message(message)
        self.assertEqual((await self.store.execute('SELECT xp FROM experience'))[0][0], 20)

    async def test_leaderboard_is_server_scoped(self):
        await self.store.execute('INSERT INTO experience VALUES (1,10,20,0)')
        await self.store.execute('INSERT INTO experience VALUES (2,99,1000,0)')
        guild = SimpleNamespace(id=1, get_member=lambda identifier: SimpleNamespace(display_name='서버멤버') if identifier == 10 else None)
        interaction = SimpleNamespace(guild=guild, response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock()))
        await self.cog.leaderboard.callback(self.cog, interaction)
        embed = interaction.followup.send.call_args.kwargs['embed']
        text = str(embed.to_dict())
        self.assertIn('서버멤버', text)
        self.assertNotIn('<@10>', text)
        self.assertNotIn('<@99>', text)

    async def test_config_requires_management_permission(self):
        interaction = SimpleNamespace(permissions=discord.Permissions())
        for check in self.cog.serverconfig.checks:
            with self.assertRaises(discord.app_commands.MissingPermissions):
                await check(interaction)

    async def test_channel_logs_display_names_for_creation_and_deletion(self):
        channel = SimpleNamespace(id=12345, name='테스트-채널', guild=SimpleNamespace(id=1))
        for event, title in ((self.cog.on_guild_channel_create, '채널 생성'), (self.cog.on_guild_channel_delete, '채널 삭제')):
            with patch.object(self.cog, 'event', new_callable=AsyncMock) as log:
                await event(channel)
                log.assert_awaited_once_with(channel.guild, title, '채널 이름: 테스트-채널')


if __name__ == '__main__':
    unittest.main()
