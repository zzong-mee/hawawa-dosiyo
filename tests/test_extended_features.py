import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from bot.cogs.announcements import Announcements
from bot.cogs.automation import Automation, render_template
from bot.cogs.general import HelpPages
from bot.cogs.giveaways import Giveaways
from bot.cogs.moderation_records import ModerationRecords
from bot.cogs.reminders import Reminders
from bot.cogs.role_automation import RoleAutomation
from bot.cogs.suggestions import Suggestions, SuggestionView
from bot.cogs.level_rewards import LevelRewards
from bot.main import HawawaBot
from bot.storage import Store


class ExtendedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'new.db'
        self.store = Store(self.path)
        self.bot = SimpleNamespace(intents=SimpleNamespace(members=True, message_content=True))

    async def asyncTearDown(self):
        self.temp.cleanup()

    def interaction(self, guild=1, user=10):
        return SimpleNamespace(
            guild=SimpleNamespace(id=guild, name='Server', owner_id=99),
            user=SimpleNamespace(id=user, display_name='Tester', top_role=10),
            permissions=discord.Permissions(manage_messages=True, manage_guild=True, manage_roles=True),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_warning_scope_and_soft_revocation(self):
        cog = ModerationRecords(self.bot, self.store)
        interaction = self.interaction()
        target = SimpleNamespace(guild=interaction.guild, id=20, top_role=1)
        await cog.modcase.callback(cog, interaction, 'warn', target, 'reason')
        row = (await self.store.execute('SELECT id FROM moderation_cases'))[0][0]
        other = self.interaction(guild=2)
        await cog.modcase.callback(cog, other, 'revoke', case_id=row)
        self.assertEqual((await self.store.execute('SELECT revoked FROM moderation_cases'))[0][0], 0)
        await cog.modcase.callback(cog, interaction, 'revoke', case_id=row)
        self.assertEqual((await self.store.execute('SELECT moderator,reason,revoked FROM moderation_cases'))[0], (10, 'reason', 10))

    async def test_warning_cannot_target_owner_or_higher(self):
        cog = ModerationRecords(self.bot, self.store)
        interaction = self.interaction()
        for user, role in ((99, 1), (20, 10), (10, 1)):
            target = SimpleNamespace(guild=interaction.guild, id=user, top_role=role)
            await cog.modcase.callback(cog, interaction, 'warn', target, 'reason')
        self.assertFalse(self.path.exists())

    def test_template_is_fixed_placeholder_only(self):
        user = SimpleNamespace(display_name='{server}')
        guild = SimpleNamespace(name='Server')
        self.assertEqual(render_template('{user} {server} {user.id}', user, guild), '{server} Server {user.id}')

    async def test_trigger_scope_casefold_and_cooldown(self):
        cog = Automation(self.bot, self.store)
        interaction = self.interaction()
        await cog.trigger.callback(cog, interaction, 'set', 'Hello', 'Hi {user}')
        channel = SimpleNamespace(id=2, send=AsyncMock())
        message = SimpleNamespace(guild=interaction.guild, author=SimpleNamespace(bot=False, display_name='Tester'), webhook_id=None, content=' HELLO ', channel=channel)
        await cog.on_message(message)
        await cog.on_message(message)
        channel.send.assert_awaited_once()
        self.assertEqual(channel.send.call_args.args[0], 'Hi Tester')
        message.guild = SimpleNamespace(id=3, name='Other')
        await cog.on_message(message)
        channel.send.assert_awaited_once()

    async def test_trigger_requires_content_intent(self):
        self.bot.intents.message_content = False
        cog = Automation(self.bot, self.store)
        await cog.trigger.callback(cog, self.interaction(), 'set', 'hi', 'hello')
        self.assertFalse(self.path.exists())

    async def test_delayed_roles_persist_and_assign_after_restart(self):
        role = SimpleNamespace(id=30)
        member = SimpleNamespace(id=20, bot=False, add_roles=AsyncMock())
        guild = SimpleNamespace(id=1, get_role=lambda identifier: role, fetch_member=AsyncMock(return_value=member))
        member.guild = guild
        self.bot.get_guild = lambda identifier: guild
        await self.store.execute('INSERT INTO delayed_roles VALUES (1,30,60)')
        cog = RoleAutomation(self.bot, self.store)
        with patch('bot.cogs.role_automation.time.time', return_value=100):
            await cog.on_member_join(member)
        restarted = RoleAutomation(self.bot, Store(self.path))
        with patch('bot.cogs.role_automation.safe_role', return_value=True):
            await restarted.assign_once(159)
            member.add_roles.assert_not_awaited()
            await restarted.assign_once(160)
            member.add_roles.assert_awaited_once()
            await restarted.assign_once(161)
            member.add_roles.assert_awaited_once()

    async def test_role_restore_excludes_temporary_roles(self):
        await self.store.set(1, 'role_restore', 'on')
        await self.store.execute('INSERT INTO temporary_roles VALUES (1,20,30,999)')
        member = SimpleNamespace(id=20, bot=False, guild=SimpleNamespace(id=1), roles=[SimpleNamespace(id=30), SimpleNamespace(id=40)])
        cog = RoleAutomation(self.bot, self.store)
        with patch('bot.cogs.role_automation.safe_role', return_value=True):
            await cog.on_member_remove(member)
        roles = json.loads((await self.store.execute('SELECT roles FROM saved_roles'))[0][0])
        self.assertEqual(roles, [40])

    async def test_repeated_reminder_reschedules_without_catchup_spam(self):
        user = SimpleNamespace(send=AsyncMock())
        bot = SimpleNamespace(fetch_user=AsyncMock(return_value=user))
        await self.store.execute("INSERT INTO reminders(guild,user,text,due) VALUES (1,20,'hello',100)")
        await self.store.execute('INSERT INTO reminder_repeats VALUES (1,5)')
        cog = Reminders(bot, self.store)
        await cog.deliver_once(1000)
        user.send.assert_awaited_once()
        self.assertEqual((await self.store.execute('SELECT state,due,attempts FROM reminders'))[0], ('pending', 1300, 0))
        await cog.deliver_once(1001)
        user.send.assert_awaited_once()

    async def test_reroll_excludes_previous_winner_and_other_guild(self):
        await self.store.execute("INSERT INTO giveaways(guild,message,channel,prize,due,count,result,announced) VALUES (1,100,20,'Prize',1000,1,'[10]',1)")
        for user in (10, 20):
            await self.store.execute('INSERT INTO giveaway_entries VALUES (1,100,?)', (user,))
        cog = Giveaways(self.bot, self.store)
        with patch('bot.cogs.giveaways.time.time', return_value=1001):
            await cog.giveaway.callback(cog, self.interaction(guild=2), 'reroll', message_id='100')
            self.assertEqual((await self.store.execute('SELECT result FROM giveaways'))[0][0], '[10]')
            await cog.giveaway.callback(cog, self.interaction(), 'reroll', message_id='100')
            self.assertEqual((await self.store.execute('SELECT result,announced FROM giveaways'))[0], ('[20]', 0))

    async def test_sticky_rate_limit_and_previous_post_replacement(self):
        channel = Mock(spec=discord.TextChannel)
        channel.id = 2
        channel.send = AsyncMock(return_value=SimpleNamespace(id=200))
        delete = AsyncMock()
        channel.get_partial_message.return_value = SimpleNamespace(delete=delete)
        await self.store.execute("INSERT INTO sticky_messages VALUES (1,2,'Notice',100,0)")
        message = SimpleNamespace(guild=SimpleNamespace(id=1, name='Server'), channel=channel, author=SimpleNamespace(bot=False, display_name='Tester'), webhook_id=None)
        cog = Announcements(self.bot, self.store)
        with patch('bot.cogs.announcements.time.time', return_value=100):
            await cog.on_message(message)
            await cog.on_message(message)
        channel.send.assert_awaited_once()
        delete.assert_awaited_once()

    async def test_help_navigation_and_owner_check(self):
        pages = [discord.Embed(title=str(index)) for index in range(3)]
        view = HelpPages(pages, 10)
        interaction = SimpleNamespace(user=SimpleNamespace(id=20), response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()))
        self.assertFalse(await view.interaction_check(interaction))
        interaction.user.id = 10
        self.assertTrue(await view.interaction_check(interaction))
        await view.move(interaction, 1)
        self.assertEqual(view.index, 1)
        await view.move(interaction, 10)
        self.assertEqual(view.index, 2)
        self.assertTrue(view.children[1].disabled)
        view.stop()

    async def test_management_commands_enforce_permissions(self):
        interaction = self.interaction()
        interaction.permissions = discord.Permissions()
        for cog, command in ((ModerationRecords(self.bot), 'modcase'), (Automation(self.bot), 'trigger'), (Automation(self.bot), 'embed'), (RoleAutomation(self.bot), 'roleautomation'), (Announcements(self.bot), 'sticky')):
            for check in getattr(cog, command).checks:
                with self.assertRaises(discord.app_commands.MissingPermissions):
                    await check(interaction)

    async def test_sync_scope_off_and_test_requirement(self):
        for scope in ('off', 'test'):
            with patch.dict(os.environ, {'COMMAND_SYNC_SCOPE': scope, 'TEST_GUILD_ID': ''}):
                async with HawawaBot() as bot:
                    with patch.object(bot.tree, 'sync', new_callable=AsyncMock) as sync:
                        if scope == 'test':
                            with self.assertRaises(RuntimeError):
                                await bot.setup_hook()
                        else:
                            await bot.setup_hook()
                        sync.assert_not_awaited()

    async def test_schema_version_protects_future_database(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute('PRAGMA user_version=99')
        with self.assertRaises(RuntimeError):
            await self.store.get(1, 'test')

    async def test_suggestion_votes_change_without_duplicates(self):
        await self.store.execute('INSERT INTO suggestions(guild,message,channel,author) VALUES (1,100,2,20)')
        cog = Suggestions(self.bot, self.store)
        view = SuggestionView(cog)
        self.assertTrue(view.is_persistent())
        interaction = self.interaction()
        interaction.user.bot = False
        interaction.message = SimpleNamespace(id=100, edit=AsyncMock())
        await view.vote(interaction, 1)
        await view.vote(interaction, -1)
        self.assertEqual(await self.store.execute('SELECT vote FROM suggestion_votes'), [(-1,)])
        await view.vote(interaction, 0)
        self.assertEqual(await self.store.execute('SELECT * FROM suggestion_votes'), [])
        await self.store.execute("UPDATE suggestions SET status='approve'")
        await view.vote(interaction, 1)
        self.assertEqual(await self.store.execute('SELECT * FROM suggestion_votes'), [])
        view.stop()

    async def test_suggestion_moderation_is_guild_scoped(self):
        await self.store.execute('INSERT INTO suggestions(guild,message,channel,author) VALUES (1,100,2,20)')
        cog = Suggestions(self.bot, self.store)
        await cog.suggestion.callback(cog, self.interaction(guild=2), 'approve', '100')
        self.assertEqual((await self.store.execute('SELECT status FROM suggestions'))[0][0], 'pending')

    async def test_suggestion_decision_displays_moderator_nickname(self):
        cog = Suggestions(self.bot, self.store)
        for action in ('approve', 'reject'):
            await self.store.execute("INSERT OR REPLACE INTO suggestions(guild,message,channel,author) VALUES (1,100,2,20)")
            interaction = self.interaction()
            interaction.user.display_name = '테스트닉네임'
            channel = Mock(spec=discord.TextChannel)
            edit = AsyncMock()
            channel.get_partial_message.return_value = SimpleNamespace(edit=edit)
            interaction.guild.get_channel = lambda identifier: channel
            await cog.suggestion.callback(cog, interaction, action, '100', '테스트')
            content = edit.call_args.kwargs['content']
            self.assertIn('처리자: 테스트닉네임', content)
            self.assertNotIn('처리자 ID', content)
            self.assertEqual(edit.call_args.kwargs['allowed_mentions'].to_dict()['parse'], [])

    async def test_level_rewards_are_scoped_and_check_role_safety(self):
        await self.store.execute('INSERT INTO level_roles VALUES (1,1,30)')
        await self.store.execute('INSERT INTO level_roles VALUES (2,1,40)')
        role = object()
        member = Mock(spec=discord.Member)
        member.guild = SimpleNamespace(id=1, get_role=lambda identifier: role)
        member.roles = []
        member.add_roles = AsyncMock()
        cog = LevelRewards(self.bot, self.store)
        with patch.dict(LevelRewards.award.__globals__, {'safe_role': lambda guild, role: False}):
            await cog.award(member, 100)
            member.add_roles.assert_not_awaited()
        with patch.dict(LevelRewards.award.__globals__, {'safe_role': lambda guild, role: True}):
            await cog.award(member, 100)
            member.add_roles.assert_awaited_once()
        member.add_roles.reset_mock()
        await cog.award(member, 90)
        member.add_roles.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
