"""Environment-backed Ollama configuration."""

from dataclasses import dataclass
import os


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise RuntimeError(f"{name} must be greater than zero")
    return parsed


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model_normal: str = "qwen3.5:4b"
    model_gaming: str = "qwen3.5:4b"
    thinking_enabled: bool = False
    num_ctx: int = 4096
    num_predict: int = 256
    keep_alive: str = "5m"
    max_concurrent: int = 1
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls):
        return cls(
            base_url=os.getenv("OLLAMA_BASE_URL", cls.base_url).strip().rstrip("/"),
            model_normal=os.getenv("OLLAMA_MODEL_NORMAL", cls.model_normal).strip(),
            model_gaming=os.getenv("OLLAMA_MODEL_GAMING", cls.model_gaming).strip(),
            thinking_enabled=os.getenv("LLM_THINKING_ENABLED", "false").strip().lower() == "true",
            num_ctx=_positive_int("LLM_NUM_CTX", cls.num_ctx),
            num_predict=_positive_int("LLM_NUM_PREDICT", cls.num_predict),
            keep_alive=os.getenv("LLM_KEEP_ALIVE", cls.keep_alive).strip(),
            max_concurrent=_positive_int("LLM_MAX_CONCURRENT", cls.max_concurrent),
            timeout_seconds=_positive_int("LLM_TIMEOUT_SECONDS", cls.timeout_seconds),
        )
