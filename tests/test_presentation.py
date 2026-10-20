import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from bot.cogs.community import Community
from bot.cogs.extras import Extras
from bot.cogs.moderation_records import ModerationRecords
from bot.cogs.server_events import ServerEvents
from bot.cogs.utility import Utility
from bot.presentation import channel_name, make_embed, role_name, text_name, user_names
from bot.storage import Store


def assert_embed_limits(test, embed):
    test.assertLessEqual(len(embed), 6000)
    test.assertLessEqual(len(embed.fields), 25)
    for field in embed.fields:
        test.assertLessEqual(len(field.name), 256)
        test.assertLessEqual(len(field.value), 1024)


class PresentationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.db')

    async def asyncTearDown(self):
        self.temp.cleanup()

    def interaction(self, guild):
        return SimpleNamespace(
            guild=guild, user=SimpleNamespace(id=99999999999999999, display_name='운영자'),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    def test_names_escape_formatting_and_missing_entities(self):
        name = text_name(SimpleNamespace(display_name='**관리자** @everyone'))
        self.assertNotIn('@everyone', name)
        self.assertIn('\\*', name)
        guild = SimpleNamespace(get_channel=lambda identifier: None, get_role=lambda identifier: None)
        self.assertNotIn('123456789', channel_name(guild, 123456789))
        self.assertNotIn('123456789', role_name(guild, 123456789))

    async def test_user_resolution_deduplicates_and_prefers_guild_names(self):
        member = SimpleNamespace(display_name='서버 닉네임')
        guild = SimpleNamespace(get_member=Mock(return_value=member), fetch_member=AsyncMock())
        result = await user_names(guild, [10, 10])
        self.assertEqual(result, {10: '서버 닉네임'})
        guild.get_member.assert_called_once_with(10)
        guild.fetch_member.assert_not_awaited()

    async def test_user_resolution_fetches_missing_member_and_handles_departure(self):
        guild = SimpleNamespace(get_member=lambda identifier: None, fetch_member=AsyncMock(return_value=SimpleNamespace(display_name='실시간 닉네임')))
        self.assertEqual((await user_names(guild, [10]))[10], '실시간 닉네임')
        guild.fetch_member.side_effect = discord.NotFound(SimpleNamespace(status=404, reason='Not Found'), 'gone')
        bot = SimpleNamespace(get_user=lambda identifier: SimpleNamespace(name='계정이름'))
        self.assertEqual((await user_names(guild, [10], bot))[10], '계정이름')
        result = (await user_names(guild, [123456789]))[123456789]
        self.assertNotIn('123456789', result)
        self.assertIn('확인할 수 없는', result)

    def test_shared_cards_have_brand_and_state_colors(self):
        pending = make_embed(title='새 건의', kind='social')
        done = make_embed(title='추첨 마감', kind='success')
        self.assertNotEqual(pending.color, done.color)
        self.assertTrue(pending.author.name)
        self.assertTrue(done.footer.text)
        self.assertIsNotNone(done.timestamp)
        assert_embed_limits(self, pending)

    async def test_team_cards_keep_all_long_names_within_discord_limits(self):
        cog = Utility()
        interaction = self.interaction(None)
        names = ['*' * 37 + f'{index:02}' for index in range(40)]
        await cog.randomteam.callback(cog, interaction, ','.join(names), 2)
        embed = interaction.response.send_message.call_args.kwargs['embed']
        assert_embed_limits(self, embed)
        lines = [line for field in embed.fields for line in field.value.splitlines()]
        self.assertEqual(len(lines), 40)
        self.assertEqual(len(set(lines)), 40)

    async def test_member_listing_uses_names_without_overflow(self):
        members = [SimpleNamespace(display_name='*' * 30 + str(index), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)) for index in range(25)]
        guild = SimpleNamespace(chunked=True, members=members)
        cog = Extras(SimpleNamespace(intents=SimpleNamespace(members=True)))
        interaction = self.interaction(guild)
        await cog.members.callback(cog, interaction, 'oldest', 25)
        embed = interaction.response.send_message.call_args.kwargs['embed']
        assert_embed_limits(self, embed)
        self.assertEqual(sum(len(field.value.splitlines()) for field in embed.fields), 25)

    async def test_channel_settings_and_auto_role_use_names(self):
        channel_id, role_id = 11111111111111111, 22222222222222222
        guild = SimpleNamespace(id=1, get_channel=lambda identifier: SimpleNamespace(name='입장안내'), get_role=lambda identifier: SimpleNamespace(name='일반멤버'))
        cog = Community(SimpleNamespace(), self.store)
        await self.store.set(1, 'welcome', str(channel_id))
        await self.store.set(1, 'autorole', str(role_id))
        interaction = self.interaction(guild)
        await cog.welcome.callback(cog, interaction)
        self.assertIn('#입장안내', interaction.followup.send.call_args.args[0])
        self.assertNotIn(str(channel_id), interaction.followup.send.call_args.args[0])
        await cog.autorole.callback(cog, interaction)
        self.assertIn('일반멤버', interaction.followup.send.call_args.args[0])
        self.assertNotIn(str(role_id), interaction.followup.send.call_args.args[0])

    async def test_rank_displays_name_and_progress(self):
        guild = SimpleNamespace(id=1)
        cog = ServerEvents(SimpleNamespace(), self.store)
        interaction = self.interaction(guild)
        await self.store.execute('INSERT INTO experience VALUES (1,?,135,0)', (interaction.user.id,))
        await cog.rank.callback(cog, interaction)
        embed = interaction.followup.send.call_args.kwargs['embed']
        output = str(embed.to_dict())
        self.assertIn('운영자', output)
        self.assertIn('35%', output)
        self.assertNotIn(str(interaction.user.id), output)
        assert_embed_limits(self, embed)

    async def test_warning_cards_resolve_all_actors_and_fit_limits(self):
        target, moderator, revoker = 11111111111111111, 22222222222222222, 33333333333333333
        names = {target: '대상닉네임', moderator: '처리닉네임', revoker: '취소닉네임'}
        guild = SimpleNamespace(id=1, get_member=lambda identifier: SimpleNamespace(display_name=names[identifier]))
        for _ in range(10):
            await self.store.execute('INSERT INTO moderation_cases (guild,user,moderator,reason,created,revoked) VALUES (1,?,?,?,?,?)', (target, moderator, '사유' * 500, 100, revoker))
        cog = ModerationRecords(SimpleNamespace(), self.store)
        interaction = self.interaction(guild)
        await cog.modcase.callback(cog, interaction, 'list')
        embed = interaction.followup.send.call_args.kwargs['embed']
        output = str(embed.to_dict())
        for identifier, name in names.items():
            self.assertIn(name, output)
            self.assertNotIn(str(identifier), output)
        assert_embed_limits(self, embed)


if __name__ == '__main__':
    unittest.main()
