import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from bot.cogs.information import Information


class InformationTests(unittest.IsolatedAsyncioTestCase):
    def interaction(self, guild=True):
        return SimpleNamespace(
            guild=SimpleNamespace(id=1) if guild else None,
            user=SimpleNamespace(id=10, display_name='Tester'),
            permissions=discord.Permissions(view_channel=True, manage_messages=False),
            app_permissions=discord.Permissions(view_channel=True, manage_messages=True),
            response=SimpleNamespace(send_message=AsyncMock()),
        )

    async def test_unicode_and_invisible_characters(self):
        cog = Information()
        interaction = self.interaction(guild=False)
        await cog.charinfo.callback(cog, interaction, '가😀\u200d\n')
        kwargs = interaction.response.send_message.call_args.kwargs
        self.assertTrue(kwargs['ephemeral'])
        self.assertEqual([f.name for f in kwargs['embed'].fields], ['U+AC00', 'U+1F600', 'U+200D', 'U+000A'])
        self.assertIn('ZERO WIDTH JOINER', kwargs['embed'].fields[2].value)
        for value in ('', 'x' * 16):
            await cog.charinfo.callback(cog, interaction, value)
            self.assertNotIn('embed', interaction.response.send_message.call_args.kwargs)

    async def test_caller_and_bot_permissions(self):
        cog = Information()
        for bot, expected in ((False, '❌ 메시지 관리'), (True, '✅ 메시지 관리')):
            interaction = self.interaction()
            await cog.permissions.callback(cog, interaction, bot=bot)
            kwargs = interaction.response.send_message.call_args.kwargs
            self.assertTrue(kwargs['ephemeral'])
            self.assertIn(expected, kwargs['embed'].fields[1].value)

    async def test_other_member_uses_channel_overwrites(self):
        cog = Information()
        interaction = self.interaction()
        channel = Mock(spec=discord.TextChannel)
        channel.permissions_for.return_value = discord.Permissions(view_channel=True, manage_messages=False)
        interaction.channel = channel
        member = SimpleNamespace(id=20, guild=interaction.guild, display_name='Other')
        await cog.permissions.callback(cog, interaction, member=member)
        channel.permissions_for.assert_called_once_with(member)
        self.assertIn('❌ 메시지 관리', interaction.response.send_message.call_args.kwargs['embed'].fields[1].value)
        member.guild = SimpleNamespace(id=2)
        channel.permissions_for.reset_mock()
        await cog.permissions.callback(cog, interaction, member=member)
        channel.permissions_for.assert_not_called()

    async def test_dm_and_conflicting_options(self):
        cog = Information()
        for interaction, member, bot in (
            (self.interaction(guild=False), None, False),
            (self.interaction(), SimpleNamespace(id=20), True),
        ):
            await cog.permissions.callback(cog, interaction, member, bot)
            kwargs = interaction.response.send_message.call_args.kwargs
            self.assertTrue(kwargs['ephemeral'])
            self.assertNotIn('embed', kwargs)


if __name__ == '__main__':
    unittest.main()
