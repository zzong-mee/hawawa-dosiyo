import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from bot.cogs.automod import AutoModeration


class AutoModTests(unittest.IsolatedAsyncioTestCase):
    def interaction(self, permission=True, rules=None):
        return SimpleNamespace(
            app_permissions=discord.Permissions(manage_guild=permission),
            guild=SimpleNamespace(fetch_automod_rules=AsyncMock(return_value=rules or []), create_automod_rule=AsyncMock()),
            user=SimpleNamespace(id=10),
            response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_keyword_creation(self):
        cog = AutoModeration(SimpleNamespace(user=SimpleNamespace(id=99)))
        interaction = self.interaction()
        await cog.automod.callback(cog, interaction, 'keywords', 'set', 'a, b')
        kwargs = interaction.guild.create_automod_rule.call_args.kwargs
        self.assertEqual(kwargs['trigger'].keyword_filter, ['a', 'b'])
        self.assertTrue(kwargs['enabled'])
        self.assertEqual(kwargs['actions'][0].type, discord.AutoModRuleActionType.block_message)

    async def test_does_not_edit_other_rules(self):
        cog = AutoModeration(SimpleNamespace(user=SimpleNamespace(id=99)))
        unrelated = SimpleNamespace(name='Hawawa:99:keywords', creator_id=88, edit=AsyncMock())
        interaction = self.interaction(rules=[unrelated])
        await cog.automod.callback(cog, interaction, 'keywords', 'disable')
        unrelated.edit.assert_not_awaited()

    async def test_missing_bot_permission_and_invalid_input(self):
        cog = AutoModeration(SimpleNamespace(user=SimpleNamespace(id=99)))
        for permission, words in ((False, 'a'), (True, 'a,')):
            interaction = self.interaction(permission=permission)
            await cog.automod.callback(cog, interaction, 'keywords', 'set', words)
            interaction.guild.fetch_automod_rules.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
