"""Repeatable, UTF-8-safe quality evaluation for a local Ollama model."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from bot.ai.character import character_prompt

MODEL = "qwen3.5:9b"
KEEP_ALIVE = "5m"
BASE_OPTIONS = {"num_ctx": 4096, "num_predict": 256}
CONDITIONS = ("default", "temperature=0.3")
SUSPECT_RE = re.compile("�|\\?{3,}")


def load_questions(path: Path) -> tuple[list[str], str, list[str]]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    data = json.loads(text)
    if not isinstance(data, list) or not all(isinstance(q, str) for q in data):
        raise ValueError("question file must contain a JSON array of strings")
    warnings = [f"question {i + 1} contains a suspicious encoding pattern" for i, q in enumerate(data) if SUSPECT_RE.search(q)]
    return data, digest, warnings


def options_for(condition: str) -> dict[str, Any]:
    options = dict(BASE_OPTIONS)
    if condition == "temperature=0.3":
        options["temperature"] = 0.3
    elif condition != "default":
        raise ValueError(f"unknown condition: {condition}")
    return options


def case_order(repeat: int) -> tuple[str, str]:
    return CONDITIONS if repeat % 2 == 1 else tuple(reversed(CONDITIONS))


async def run_evaluation(*, questions: list[str], question_sha256: str, base_url: str, repeats: int, timeout: float) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        for repeat in range(1, repeats + 1):
            for question in questions:
                for condition in case_order(repeat):
                    options = options_for(condition)
                    payload = {
                        "model": MODEL,
                        "messages": [{"role": "system", "content": character_prompt()}, {"role": "user", "content": question}],
                        "stream": False,
                        "think": False,
                        "keep_alive": KEEP_ALIVE,
                        "options": options,
                    }
                    started = time.perf_counter()
                    item: dict[str, Any] = {
                        "repeat": repeat,
                        "condition": condition,
                        "question_original": question,
                        "question_sent": payload["messages"][1]["content"],
                        "question_matches_source": payload["messages"][1]["content"] == question,
                        "options": options,
                    }
                    try:
                        response = await client.post("/api/chat", json=payload)
                        response.raise_for_status()
                        data = response.json()
                        item.update({
                            "response": data.get("message", {}).get("content"),
                            "elapsed_seconds": round(time.perf_counter() - started, 4),
                            "done_reason": data.get("done_reason"),
                            "eval_count": data.get("eval_count"),
                            "eval_duration": data.get("eval_duration"),
                            "prompt_eval_count": data.get("prompt_eval_count"),
                            "error": None,
                        })
                    except (httpx.TimeoutException, httpx.ConnectError) as exc:
                        item.update({"elapsed_seconds": round(time.perf_counter() - started, 4), "error": f"{type(exc).__name__}: {exc}"})
                    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                        item.update({"elapsed_seconds": round(time.perf_counter() - started, 4), "error": f"{type(exc).__name__}: {exc}"})
                    results.append(item)
    return {"model": MODEL, "question_sha256": question_sha256, "base_url": base_url, "repeats": repeats, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path(__file__).with_name("ollama_eval_questions.json"))
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "hawawa-ollama-quality-eval.json")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    questions, digest, warnings = load_questions(args.questions)
    for warning in warnings:
        print(f"WARNING: {warning}")
    report = asyncio.run(run_evaluation(questions=questions, question_sha256=digest, base_url=args.base_url, repeats=args.repeats, timeout=args.timeout))
    report["started_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.output} ({len(report['results'])} requests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
