import unittest
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot.ai.client import OllamaError
from bot.cogs.ai_chat import AIChat, mention_prompt, safe_reply
from bot.main import HawawaBot


class AIChatTests(unittest.IsolatedAsyncioTestCase):
    def test_ai_requires_message_content_intent(self):
        with patch.dict(os.environ, {"AI_ENABLED": "true", "ENABLE_MESSAGE_CONTENT": "false"}):
            with self.assertRaisesRegex(RuntimeError, "Message Content Intent"):
                HawawaBot()

    def setUp(self):
        self.bot_user = SimpleNamespace(id=99)

    def message(self, *, guild=True, author_bot=False, mentions=None, content="<@99> 안녕"):
        class Typing:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
        return SimpleNamespace(
            guild=object() if guild else None,
            author=SimpleNamespace(bot=author_bot), webhook_id=None,
            mentions=mentions or [], content=content,
            channel=SimpleNamespace(typing=lambda: Typing()),
        )

    def test_only_direct_bot_mention_produces_prompt(self):
        self.assertEqual(mention_prompt(self.message(mentions=[self.bot_user]), self.bot_user), "안녕")
        self.assertIsNone(mention_prompt(self.message(mentions=[]), self.bot_user))
        self.assertIsNone(mention_prompt(self.message(author_bot=True, mentions=[self.bot_user]), self.bot_user))
        self.assertIsNone(mention_prompt(self.message(guild=False, mentions=[self.bot_user]), self.bot_user))

    def test_empty_mention_gets_short_prompt_and_reply_is_limited(self):
        self.assertIn("인사", mention_prompt(self.message(mentions=[self.bot_user], content="<@99>"), self.bot_user))
        self.assertEqual(len(safe_reply("x" * 3000)), 2000)
        self.assertTrue(safe_reply(""))

    async def test_listener_replies_with_safe_mentions(self):
        message = self.message(mentions=[self.bot_user])
        message.reply = AsyncMock()
        bot = SimpleNamespace(user=self.bot_user, loop=SimpleNamespace(create_task=AsyncMock()))
        cog = AIChat.__new__(AIChat)
        cog.bot = bot
        cog.client = SimpleNamespace(generate=AsyncMock(return_value="안녕 <@123>"))
        await cog.on_message(message)
        message.reply.assert_awaited_once()
        self.assertEqual(message.reply.await_args.args[0], "안녕 <@123>")
        self.assertFalse(message.reply.await_args.kwargs["mention_author"])
        self.assertFalse(message.reply.await_args.kwargs["allowed_mentions"].everyone)
        self.assertFalse(message.reply.await_args.kwargs["allowed_mentions"].users)
        self.assertFalse(message.reply.await_args.kwargs["allowed_mentions"].roles)

    async def test_listener_handles_ollama_failure_without_details(self):
        message = self.message(mentions=[self.bot_user]); message.reply = AsyncMock()
        bot = SimpleNamespace(user=self.bot_user, loop=SimpleNamespace(create_task=AsyncMock()))
        cog = AIChat.__new__(AIChat); cog.bot = bot
        cog.client = SimpleNamespace(generate=AsyncMock(side_effect=OllamaError("secret URL")))
        await cog.on_message(message)
        self.assertNotIn("secret URL", message.reply.await_args.args[0])

