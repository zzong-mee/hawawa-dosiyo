import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
from discord import app_commands

from bot.cogs.community import Community, safe_role
from bot.storage import Store


class CommunityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'new.db'
        self.store = Store(self.path)
        self.cog = Community(SimpleNamespace(intents=SimpleNamespace(members=False)), self.store)

    async def asyncTearDown(self):
        self.directory.cleanup()

    def interaction(self, guild=1, manager=True):
        return SimpleNamespace(
            guild=SimpleNamespace(id=guild),
            permissions=discord.Permissions(manage_guild=manager),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_settings_are_isolated_and_persist(self):
        await self.store.set(1, 'welcome', '100')
        await self.store.set(2, 'welcome', '200')
        restarted = Store(self.path)
        self.assertEqual(await restarted.get(1, 'welcome'), '100')
        self.assertEqual(await restarted.get(2, 'welcome'), '200')
        await restarted.set(1, 'welcome', '')
        self.assertEqual(await restarted.get(2, 'welcome'), '200')

    async def test_tag_lifecycle_and_guild_isolation(self):
        interaction = self.interaction()
        await self.cog.tag.callback(self.cog, interaction, 'set', 'Rules', 'Read rules')
        restarted = Community(self.cog.bot, Store(self.path))
        await restarted.tag.callback(restarted, interaction, 'show', 'rules')
        self.assertEqual(interaction.followup.send.call_args.args[0], 'Read rules')
        other = self.interaction(guild=2)
        await restarted.tag.callback(restarted, other, 'show', 'rules')
        self.assertIn('없습니다', other.followup.send.call_args.args[0])
        await restarted.tag.callback(restarted, other, 'remove', 'rules')
        await restarted.tag.callback(restarted, interaction, 'list')
        self.assertIn('rules', interaction.followup.send.call_args.args[0])
        await restarted.tag.callback(restarted, interaction, 'remove', 'rules')
        await restarted.tag.callback(restarted, interaction, 'show', 'rules')
        self.assertIn('없습니다', interaction.followup.send.call_args.args[0])

    async def test_tag_writes_require_permission(self):
        for action in ('set', 'remove'):
            interaction = self.interaction(manager=False)
            await self.cog.tag.callback(self.cog, interaction, action, 'rules', 'value')
            interaction.response.defer.assert_not_awaited()
            self.assertIn('권한', interaction.response.send_message.call_args.args[0])
        self.assertFalse(self.path.exists())

    async def test_greeting_configuration_requires_members_intent(self):
        interaction = self.interaction()
        await self.cog.welcome.callback(self.cog, interaction, channel=SimpleNamespace(id=10))
        self.assertIn('Intent', interaction.response.send_message.call_args.args[0])
        self.assertFalse(self.path.exists())

    async def test_configuration_permissions_are_enforced(self):
        interaction = self.interaction(manager=False)
        interaction.permissions.manage_roles = False
        for command in (self.cog.welcome, self.cog.autorole):
            for predicate in command.checks:
                with self.assertRaises(app_commands.MissingPermissions):
                    await predicate(interaction)

    def test_auto_role_rejects_privilege_and_hierarchy(self):
        guild = SimpleNamespace(id=1, me=SimpleNamespace(
            guild_permissions=discord.Permissions(manage_roles=True), top_role=10))
        class Role:
            managed = False
            permissions = discord.Permissions()
            position = 2
            def __init__(self):
                self.guild = guild
            def is_default(self):
                return False
            def __lt__(self, other):
                return self.position < other
        role = Role()
        self.assertTrue(safe_role(guild, role))
        for name in ('administrator', 'manage_roles', 'manage_channels', 'ban_members', 'mention_everyone'):
            role.permissions = discord.Permissions(**{name: True})
            self.assertFalse(safe_role(guild, role))
        role.permissions = discord.Permissions()
        role.position = 10
        self.assertFalse(safe_role(guild, role))
        role.position = 2
        role.managed = True
        self.assertFalse(safe_role(guild, role))

    async def test_join_bot_ignored_and_greetings_sent(self):
        member = SimpleNamespace(bot=True)
        await self.cog.on_member_join(member)
        self.assertFalse(self.path.exists())
        channel = Mock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        guild = SimpleNamespace(id=1, name='Test Server', get_channel=lambda channel_id: channel)
        member = SimpleNamespace(bot=False, guild=guild, display_name='New Member')
        await self.store.set(1, 'welcome', '100')
        await self.cog.on_member_join(member)
        channel.send.assert_awaited_once()
        self.assertEqual(channel.send.call_args.kwargs['allowed_mentions'].to_dict()['parse'], [])


if __name__ == '__main__':
    unittest.main()
