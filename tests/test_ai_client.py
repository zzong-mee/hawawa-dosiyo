import asyncio
import unittest

import httpx

from bot.ai.client import OllamaClient, OllamaError
from bot.ai.config import OllamaConfig
from bot.ai.character import character_prompt


class AIClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_posts_non_thinking_request_and_strips_internal_thought(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"message": {"content": "<think>secret</think>안녕!"}})

        client = OllamaClient(OllamaConfig(), httpx.MockTransport(handler))
        try:
            self.assertEqual(await client.generate("안녕"), "안녕!")
            self.assertEqual(requests[0].url.path, "/api/chat")
            self.assertIn('"think":false', requests[0].content.decode())
            self.assertIn('"model":"qwen3.5:4b"', requests[0].content.decode())
        finally:
            await client.aclose()

    async def test_preserves_normal_response_without_think_marker(self):
        client = OllamaClient(
            OllamaConfig(model_normal="qwen3.5:4b"),
            httpx.MockTransport(lambda request: httpx.Response(200, json={"message": {"content": "오늘은 기분이 좋아!"}})),
        )
        try:
            self.assertEqual(await client.generate("기분 어때?"), "오늘은 기분이 좋아!")
        finally:
            await client.aclose()

    async def test_system_and_user_messages_are_separate(self):
        requests = []
        client = OllamaClient(
            OllamaConfig(),
            httpx.MockTransport(lambda request: (requests.append(request) or httpx.Response(200, json={"message": {"content": "응"}}))),
        )
        try:
            await client.generate("안녕", system=character_prompt())
            payload = __import__("json").loads(requests[0].content)
            self.assertEqual(payload["messages"][0]["role"], "system")
            self.assertIn("도시요", payload["messages"][0]["content"])
            self.assertEqual(payload["messages"][1], {"role": "user", "content": "안녕"})
        finally:
            await client.aclose()

    def test_character_name_and_persona_guardrails(self):
        prompt = character_prompt()
        self.assertIn("\ub3c4\uc2dc\uc694", prompt)
        self.assertIn("\ub098\ub978\ud558\uace0 \ub2a5\uae00\ub9de\uc740 \ucc9c\uc7ac \ud5c8\ub2f9 \uad50\uc218 \ub204\ub098", prompt)
        self.assertIn("\uc790\uc5f0\uc2a4\ub7ec\uc6b4 \ud55c\uad6d\uc5b4 \ubc18\ub9d0", prompt)
        self.assertIn("\ub0b4\ubd80 \ucd94\ub860", prompt)
        self.assertIn("\uc2e4\uc81c \uacbd\ud5d8", prompt)
        self.assertIn("\uc9c0\uc5b4\ub0b4\uac70\ub098", prompt)

    def test_persona_is_one_character_with_contextual_facets(self):
        prompt = character_prompt()
        self.assertIn("\uc9c0\uc2dd \uc9c8\ubb38\uc5d0\ub294 \uc815\ud655\ud558\uace0 \uc9c0\uc801\uc778 \uad50\uc218\ucc98\ub7fc", prompt)
        self.assertIn("\uc77c\uc0c1 \ub300\ud654\uc5d0\ub294 \uc5ec\uc720\ub86d\uace0 \ub2e4\uc815\ud55c \ub204\ub098\ucc98\ub7fc", prompt)
        self.assertIn("\uc7a5\ub09c\uc5d0\ub294 \uac00\ubccd\uace0 \ub2a5\uae00\ub9de\uc740 \uce5c\uad6c\ucc98\ub7fc", prompt)
        self.assertIn("\ubcc4\ub3c4\uc758 \uc778\uaca9\uc774\ub098 \uc0c1\ud0dc \uc804\ud658\uc774 \uc544\ub2c8\ub77c", prompt)
        self.assertIn("\uc911\uad6d\uc5b4\u00b7\uc77c\ubcf8\uc5b4\u00b7\uc601\uc5b4\ub97c \ubd88\ud544\uc694\ud558\uac8c \uc11e\uc9c0 \ub9c8", prompt)

    def test_custom_prompt_still_overrides_default(self):
        self.assertEqual(character_prompt("  custom rules  "), "custom rules")

    async def test_limits_concurrent_requests(self):
        active = 0
        peak = 0

        async def handler(request):
            nonlocal active, peak
            active += 1; peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return httpx.Response(200, json={"message": {"content": "ok"}})

        client = OllamaClient(OllamaConfig(max_concurrent=1), httpx.MockTransport(handler))
        try:
            await asyncio.gather(*(client.generate("x") for _ in range(3)))
            self.assertEqual(peak, 1)
        finally:
            await client.aclose()

    async def test_http_errors_are_safe(self):
        client = OllamaClient(OllamaConfig(), httpx.MockTransport(lambda request: httpx.Response(503)))
        try:
            with self.assertRaises(OllamaError):
                await client.generate("x")
        finally:
            await client.aclose()
