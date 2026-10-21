import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from tools.ollama_quality_eval import case_order, load_questions, options_for, run_evaluation


class OllamaQualityEvalTests(unittest.TestCase):
    def test_loads_utf8_questions_and_hash(self):
        path = Path(__file__).parents[1] / "tools" / "ollama_eval_questions.json"
        questions, digest, warnings = load_questions(path)
        self.assertEqual(len(questions), 12)
        self.assertEqual(questions[0], "안녕!")
        self.assertEqual(len(digest), 64)
        self.assertEqual(warnings, [])

    def test_detects_suspicious_encoding_patterns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.json"
            path.write_text(json.dumps(["정상?", "깨짐 �", "???"], ensure_ascii=False), encoding="utf-8")
            _, _, warnings = load_questions(path)
        self.assertEqual(len(warnings), 2)

    def test_options_and_alternating_order(self):
        self.assertEqual(options_for("default"), {"num_ctx": 4096, "num_predict": 256})
        self.assertEqual(options_for("temperature=0.3"), {"num_ctx": 4096, "num_predict": 256, "temperature": 0.3})
        self.assertEqual(case_order(1), ("default", "temperature=0.3"))
        self.assertEqual(case_order(2), ("temperature=0.3", "default"))

    def test_records_exact_question_options_and_errors(self):
        requests = []

        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"message": {"content": "안녕!"}, "done_reason": "stop", "eval_count": 1})

        async def run():
            transport = httpx.MockTransport(handler)
            # Patch the constructor only for this isolated mock run.
            original = httpx.AsyncClient
            httpx.AsyncClient = lambda **kwargs: original(transport=transport, **kwargs)
            try:
                return await run_evaluation(questions=["안녕!"], question_sha256="a" * 64, base_url="http://test", repeats=2, timeout=1)
            finally:
                httpx.AsyncClient = original

        report = asyncio.run(run())
        self.assertEqual([r["condition"] for r in report["results"]], ["default", "temperature=0.3", "temperature=0.3", "default"])
        self.assertTrue(all(r["question_matches_source"] for r in report["results"]))
        self.assertNotIn("temperature", requests[0]["options"])
        self.assertEqual(requests[1]["options"]["temperature"], 0.3)
        self.assertEqual(report["results"][0]["done_reason"], "stop")


if __name__ == "__main__":
    unittest.main()
