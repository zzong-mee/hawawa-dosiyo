import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from bot.cogs.moderation import Moderation
from bot.cogs.utility import Utility


class NewCommandTests(unittest.IsolatedAsyncioTestCase):
    def interaction(self, *, user_permission=True, bot_permission=True, guild=True):
        channel = Mock(spec=discord.TextChannel)
        channel.purge = AsyncMock(return_value=[object(), object()])
        return SimpleNamespace(
            guild=object() if guild else None, channel=channel,
            permissions=discord.Permissions(manage_messages=user_permission),
            app_permissions=discord.Permissions(manage_messages=bot_permission, read_message_history=True, view_channel=True),
            created_at=datetime.now(timezone.utc), user=SimpleNamespace(id=123),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_clear_denies_without_permission(self):
        cog = Moderation()
        for flags in ({'user_permission': False}, {'bot_permission': False}, {'guild': False}):
            interaction = self.interaction(**flags)
            await cog.clear.callback(cog, interaction, 5)
            interaction.channel.purge.assert_not_awaited()
            interaction.response.defer.assert_not_awaited()
            self.assertTrue(interaction.response.send_message.call_args.kwargs['ephemeral'])
        self.assertTrue(cog.clear.default_permissions.manage_messages)

    async def test_clear_scope_pins_and_result(self):
        cog = Moderation()
        interaction = self.interaction()
        await cog.clear.callback(cog, interaction, 5)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        interaction.channel.purge.assert_awaited_once()
        kwargs = interaction.channel.purge.call_args.kwargs
        self.assertEqual(kwargs['limit'], 5)
        self.assertEqual(kwargs['before'], interaction.created_at)
        self.assertFalse(kwargs['check'](SimpleNamespace(pinned=True)))
        self.assertTrue(kwargs['check'](SimpleNamespace(pinned=False)))
        self.assertIn('2개', interaction.followup.send.call_args.args[0])

    async def test_clear_http_error(self):
        cog = Moderation()
        interaction = self.interaction()
        response = SimpleNamespace(status=403, reason='Forbidden')
        interaction.channel.purge.side_effect = discord.Forbidden(response, 'Forbidden')
        await cog.clear.callback(cog, interaction, 5)
        self.assertIn('일부 메시지', interaction.followup.send.call_args.args[0])

    async def test_randomteam_balanced_and_no_duplicates(self):
        cog = Utility()
        interaction = self.interaction()
        with patch('bot.cogs.utility.random.shuffle'):
            await cog.randomteam.callback(cog, interaction, 'A,B,C,D,E', 2)
        kwargs = interaction.response.send_message.call_args.kwargs
        teams = [field.value.splitlines() for field in kwargs['embed'].fields]
        self.assertEqual(sorted(map(len, teams)), [2, 3])
        self.assertEqual(sorted(member for team in teams for member in team), list('ABCDE'))
        self.assertTrue(kwargs['ephemeral'])

    async def test_randomteam_invalid_input(self):
        cog = Utility()
        for participants, teams in (('A,A', 2), ('A,B', 3), ('A,', 2)):
            interaction = self.interaction()
            await cog.randomteam.callback(cog, interaction, participants, teams)
            self.assertNotIn('embed', interaction.response.send_message.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
