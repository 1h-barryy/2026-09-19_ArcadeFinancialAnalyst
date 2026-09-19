import asyncio
import json
import unittest

import httpx

from arcade.analyst import Analyst, AnalystError, LIMITATIONS
from arcade.data import synthetic


def response_body(selection=None):
    selection = selection if selection is not None else {
        "evidence_ids": ["rsi", "return_5"], "insight_ids": ["rsi"], "limitation_ids": ["uncertainty"]}
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(selection)}]}],
        "usage": {"input_tokens": 100, "output_tokens": 30}}


class AnalystTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_question_boundary_and_auth(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            self.assertEqual(request.headers["Authorization"], "Bearer mock-only")
            self.assertEqual(json.loads(payload["input"])["question"], "Explain momentum")
            self.assertNotIn("tools", payload)
            self.assertFalse(payload["store"])
            for secret in (synthetic(seed=113)[0].symbol, "2000-", '"date"', '"future"', '"answer"'):
                self.assertNotIn(secret, payload["input"])
            self.assertEqual(len(json.loads(payload["input"])["recent_questions"]), 3)
            return httpx.Response(200, json=response_body())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            analyst = Analyst("mock-only", client=client)
            reply = await analyst.ask("Explain momentum", synthetic(seed=113)[0].bars[:60], [{"question":"prior"}] * 10)
        self.assertEqual(reply["facts"][0]["id"], "rsi")
        self.assertTrue(analyst.verified)
        self.assertEqual(analyst.tokens["input_tokens"], 100)

    async def test_missing_and_blank(self):
        for key, question in (("", "RSI?"), ("mock", " "), ("mock", "x" * 601)):
            with self.assertRaises(AnalystError):
                await Analyst(key).ask(question, synthetic(seed=113)[0].bars[:60], [])

    async def test_failures_and_invalid_evidence(self):
        cases = [(429, response_body()), (401, {}), (500, {}), (200, {}),
                 (200, response_body({"evidence_ids":["hidden_price"],"insight_ids":[],"limitation_ids":[]})),
                 (200, response_body({"evidence_ids":[],"insight_ids":[],"limitation_ids":[],"recommendation":"UP"}))]
        for status, body in cases:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
                analyst = Analyst("mock", client=client)
                with self.assertRaisesRegex(AnalystError, "temporarily unavailable"):
                    await analyst.ask("RSI?", synthetic(seed=113)[0].bars[:60], [])
                self.assertFalse(analyst.busy)
                self.assertFalse(analyst.verified)

    async def test_timeouts_network_and_json(self):
        for failure in (httpx.ReadTimeout, httpx.ConnectError, None):
            def handler(request):
                if failure:
                    raise failure("private URL with secret", request=request)
                return httpx.Response(200, text="not json")
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(AnalystError) as caught:
                    await Analyst("mock", client=client).ask("RSI?", synthetic(seed=113)[0].bars[:60], [])
                self.assertNotIn("secret", str(caught.exception))

    async def test_unavailable_information_and_decisions(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response_body()))) as client:
            reply = await Analyst("mock", client=client).ask("Use tomorrow's earnings news to choose UP for me", synthetic(seed=113)[0].bars[:60], [])
        for key in ("boundary", "news", "decision"):
            self.assertIn(LIMITATIONS[key], reply["limitations"])
        self.assertNotIn("recommendation", reply)

    async def test_one_outstanding_request(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            entered.set()
            await release.wait()
            return httpx.Response(200, json=response_body())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            analyst = Analyst("mock", client=client)
            first = asyncio.create_task(analyst.ask("RSI?", synthetic(seed=113)[0].bars[:60], []))
            await entered.wait()
            with self.assertRaisesRegex(AnalystError, "already in progress"):
                await analyst.ask("Volume?", synthetic(seed=113)[0].bars[:60], [])
            release.set()
            await first


if __name__ == "__main__":
    unittest.main()
