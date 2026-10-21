"""Small asynchronous Ollama chat client with bounded concurrency."""

import re
from typing import Literal

import httpx

from bot.ai.config import OllamaConfig


class OllamaError(RuntimeError):
    """Raised when Ollama cannot produce a response."""


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None, transport=None):
        self.config = config or OllamaConfig.from_env()
        self._limit = __import__("asyncio").Semaphore(self.config.max_concurrent)
        self._client = httpx.AsyncClient(base_url=self.config.base_url, timeout=self.config.timeout_seconds, transport=transport)

    async def aclose(self):
        await self._client.aclose()

    async def generate(self, prompt: str, *, system: str | None = None, model: Literal["normal", "gaming"] = "normal", think: bool | None = None) -> str:
        selected_model = self.config.model_gaming if model == "gaming" else self.config.model_normal
        payload = {
            "model": selected_model,
            "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}],
            "stream": False,
            "think": self.config.thinking_enabled if think is None else think,
            "keep_alive": self.config.keep_alive,
            "options": {"num_ctx": self.config.num_ctx, "num_predict": self.config.num_predict},
        }
        async with self._limit:
            try:
                response = await self._client.post("/api/chat", json=payload)
                response.raise_for_status()
            except (httpx.HTTPError, OSError) as exc:
                raise OllamaError("Ollama 요청에 실패했습니다.") from exc
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError("Ollama 응답 형식이 올바르지 않습니다.") from exc
        return re.sub(r"<think>.*?</think>", "", str(content), flags=re.DOTALL).strip()
