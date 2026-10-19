import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot.cogs.utility import Utility, parse_options
from bot.main import HawawaBot


class UtilityTests(unittest.IsolatedAsyncioTestCase):
    def interaction(self, *, guild=True, permission=True):
        return SimpleNamespace(
            guild=object() if guild else None,
            app_permissions=discord.Permissions(send_polls=permission),
            response=SimpleNamespace(send_message=AsyncMock(), is_done=lambda: False),
        )

    async def test_registration_and_help(self):
        for guild_id in ('', '123456789012345678'):
            async with HawawaBot() as bot:
                with patch.dict(os.environ, {'TEST_GUILD_ID': guild_id}), patch.object(bot.tree, 'sync', new_callable=AsyncMock):
                    await bot.setup_hook()
                names = {'ping', 'help', 'serverinfo', 'userinfo', 'avatar', 'roll', 'vote', 'poll', 'randomteam', 'clear'}
                self.assertEqual({c.name for c in bot.tree.get_commands()}, names)
                if guild_id:
                    self.assertEqual({c.name for c in bot.tree.get_commands(guild=discord.Object(id=int(guild_id)))}, names)
                command = bot.tree.get_command('help')
                interaction = self.interaction()
                await command.callback(command.binding, interaction)
                embed = interaction.response.send_message.call_args.kwargs['embed']
                self.assertEqual({f.name for f in embed.fields}, {'/' + n for n in names})

    def test_options_validation(self):
        self.assertEqual(parse_options(' A , B ', 10, 55), ['A', 'B'])
        for text in ('A', 'A,', 'A,A', ',B', 'x' * 56 + ',B', ','.join(map(str, range(11)))):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_options(text, 10, 55)

    async def test_roll_and_vote(self):
        cog = Utility()
        interaction = self.interaction()
        with patch('bot.cogs.utility.random.randint', side_effect=[1, 6]):
            await cog.roll.callback(cog, interaction, 6, 2)
        self.assertIn('합계: 7', interaction.response.send_message.call_args.args[0])
        interaction = self.interaction()
        await cog.vote.callback(cog, interaction, 'A,')
        self.assertTrue(interaction.response.send_message.call_args.kwargs['ephemeral'])
        interaction = self.interaction()
        with patch('bot.cogs.utility.random.choice', return_value='A'):
            await cog.vote.callback(cog, interaction, 'A,B')
        self.assertEqual(interaction.response.send_message.call_args.args[0], '선택 결과: A')
        self.assertEqual(interaction.response.send_message.call_args.kwargs['allowed_mentions'].to_dict()['parse'], [])

    async def test_user_defaults_and_explicit_target(self):
        cog = Utility()
        target = SimpleNamespace(id=123, bot=False, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), display_avatar=SimpleNamespace(url='https://example.com/avatar.png'))
        for name in ('userinfo', 'avatar'):
            for explicit in (False, True):
                interaction = self.interaction(guild=False)
                interaction.user = target
                command = getattr(cog, name)
                await command.callback(cog, interaction, target if explicit else None)
                kwargs = interaction.response.send_message.call_args.kwargs
                self.assertTrue(kwargs['ephemeral'])
                if name == 'avatar':
                    self.assertEqual(kwargs['embed'].image.url, target.display_avatar.url)
                else:
                    self.assertIn('123', [f.value for f in kwargs['embed'].fields])

    async def test_poll_creation_and_guards(self):
        cog = Utility()
        interaction = self.interaction()
        await cog.poll.callback(cog, interaction, 'Lunch?', 'A,B', 2, True)
        kwargs = interaction.response.send_message.call_args.kwargs
        self.assertNotIn('ephemeral', kwargs)
        poll = kwargs['poll']
        self.assertEqual(poll.question, 'Lunch?')
        self.assertEqual([a.text for a in poll.answers], ['A', 'B'])
        self.assertTrue(poll.multiple)
        for guild, permission, question, options in ((False, True, 'Q', 'A,B'), (True, False, 'Q', 'A,B'), (True, True, ' ', 'A,B'), (True, True, 'Q', 'A,A')):
            interaction = self.interaction(guild=guild, permission=permission)
            await cog.poll.callback(cog, interaction, question, options)
            self.assertTrue(interaction.response.send_message.call_args.kwargs['ephemeral'])


if __name__ == '__main__':
    unittest.main()
