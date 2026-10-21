import asyncio
import unittest

import httpx

from bot.ai.client import OllamaClient, OllamaError
from bot.ai.config import OllamaConfig


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
