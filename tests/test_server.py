import asyncio
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx

from arcade.analyst import Analyst
from arcade.data import synthetic
from arcade.game import indexed
from arcade.server import create_app
from test_analyst import response_body


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 1000.0
        self.loads = 0
        def loader():
            self.loads += 1
            return synthetic(seed=113), "SYNTHETIC DEMO"
        self.app = create_app(loader=loader, clock=lambda: self.now)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver",
                                       headers={"X-Arcade":"1"})

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_full_three_round_flow_and_restart(self):
        state = (await self.client.post("/api/game")).json()
        for n in range(3):
            rid = state["round_id"]
            self.assertEqual(state["round"], n + 1)
            self.assertIsNone(state["result"])
            self.assertNotIn("FICTION", str(state))
            self.assertEqual((await self.client.post("/api/next", json={"round_id":rid})).status_code, 409)
            state = (await self.client.post("/api/ready", json={"round_id":rid})).json()
            self.assertEqual(state["phase"], "research")
            result = await self.client.post("/api/predict", json={"round_id":rid,"choice":"UP"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(result.json()["result"]["future"]), 5)
            self.assertEqual((await self.client.post("/api/predict", json={"round_id":rid,"choice":"UP"})).status_code, 409)
            if n < 2:
                state = (await self.client.post("/api/next", json={"round_id":rid})).json()
        self.assertTrue(result.json()["complete"])
        reset = (await self.client.post("/api/game")).json()
        self.assertEqual(reset["round"], 1)
        self.assertEqual(reset["score"], 0)
        self.assertEqual(reset["summary"], {"correct_predictions": 0, "best_combo": 0, "analyst_questions": 0})
        self.assertEqual(reset["phase"], "ready")
        self.assertEqual(reset["history"], [])
        self.assertEqual(self.loads, 1)

    async def test_no_hidden_static_files_or_cross_origin(self):
        self.assertEqual((await self.client.get("/.env")).status_code, 404)
        self.assertEqual((await self.client.get("/.local/cache/IBM.json")).status_code, 404)
        self.assertEqual((await self.client.get("/static/../.env")).status_code, 404)
        self.assertEqual((await self.client.post("/api/game", headers={"X-Arcade":"0"})).status_code, 403)
        self.assertEqual((await self.client.post("/api/game", headers={"Origin":"https://example.org"})).status_code, 403)
        self.assertEqual((await self.client.get("/", headers={"Host":"evil.example"})).status_code, 400)
        self.assertEqual((await self.client.get("/")).status_code, 200)

    async def test_timeout_refresh_and_invalid_inputs(self):
        state = (await self.client.post("/api/game")).json()
        rid = state["round_id"]
        await self.client.post("/api/ready", json={"round_id":rid})
        for question in ("", " "):
            response = await self.client.post("/api/ask", json={"round_id":rid,"question":question})
            self.assertIn(response.status_code, (422, 503))
        self.assertEqual((await self.client.post("/api/predict", json={"round_id":rid,"choice":"bad"})).status_code, 422)
        self.now += 61
        result = (await self.client.get("/api/game")).json()
        self.assertEqual(result["result"]["choice"], "No call")
        self.assertEqual(result["score"], 0)
        self.assertEqual((await self.client.post("/api/ask", json={"round_id":rid,"question":"future?"})).status_code, 409)

    async def test_slow_analyst_does_not_block_timeout_or_prediction(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            entered.set()
            await release.wait()
            return httpx.Response(200, json=response_body())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as provider:
            advisor = Analyst("mock", client=provider)
            app = create_app(loader=lambda: (synthetic(seed=113), "SYNTHETIC DEMO"), analyst=advisor, clock=lambda:self.now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"X-Arcade":"1"}) as client:
                state = (await client.post("/api/game")).json()
                rid = state["round_id"]
                await client.post("/api/ready", json={"round_id":rid})
                pending = asyncio.create_task(client.post("/api/ask", json={"round_id":rid,"question":"Momentum?"}))
                await entered.wait()
                second = await client.post("/api/ask", json={"round_id":rid,"question":"Volume?"})
                self.assertEqual(second.status_code, 409)
                self.now += 61
                state = (await client.get("/api/game")).json()
                self.assertEqual(state["result"]["choice"], "No call")
                self.assertEqual(state["summary"]["analyst_questions"], 1)
                release.set()
                self.assertEqual((await pending).status_code, 200)

    async def test_question_count_survives_history_limit_and_resets(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json=response_body()))) as provider:
            advisor = Analyst("mock", client=provider)
            app = create_app(loader=lambda: (synthetic(seed=113), "SYNTHETIC DEMO"), analyst=advisor, clock=lambda:self.now)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"X-Arcade":"1"}) as client:
                state = (await client.post("/api/game")).json()
                rid = state["round_id"]
                await client.post("/api/ready", json={"round_id": rid})
                for i in range(8):
                    advisor.next_allowed = 0
                    response = await client.post("/api/ask", json={"round_id":rid, "question":f"Momentum question {i}?"})
                    self.assertEqual(response.status_code, 200)
                state = (await client.get("/api/game")).json()
                self.assertEqual(state["summary"]["analyst_questions"], 8)
                self.assertEqual(len(state["history"]), 6)
                reset = (await client.post("/api/game")).json()
                self.assertEqual(reset["summary"]["analyst_questions"], 0)
                self.assertEqual(reset["history"], [])

    async def test_start_gate_and_failed_question_accounting(self):
        self.assertEqual((await self.client.get("/api/status")).status_code, 200)
        self.assertEqual(self.loads, 0)
        state = (await self.client.post("/api/game")).json()
        rid = state["round_id"]
        self.now += 600
        state = (await self.client.get("/api/game")).json()
        self.assertEqual(state["phase"], "ready")
        self.assertEqual(state["remaining"], 60)
        self.assertEqual(len(state["chart"]), 60)
        self.assertTrue(all(set(bar) == {"day", "open", "high", "low", "close", "volume"} for bar in state["chart"]))
        self.assertIsNone(state["result"])
        await self.client.post("/api/ready", json={"round_id":rid})
        await self.client.post("/api/ask", json={"round_id":rid, "question":" "})
        self.assertEqual((await self.client.get("/api/game")).json()["summary"]["analyst_questions"], 0)
        response = await self.client.post("/api/ask", json={"round_id":rid, "question":"Explain RSI"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual((await self.client.get("/api/game")).json()["summary"]["analyst_questions"], 1)

    async def test_demo_and_auto_fallback_replay_regenerate_without_mutating_active_game(self):
        originals, replay, other_game = (synthetic(seed=seed) for seed in (10, 20, 30))
        for mode in ("demo", "auto"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp, \
                    patch("arcade.data.synthetic", return_value=originals) as initial_generator, \
                    patch("arcade.server.synthetic", side_effect=[replay, other_game]) as replay_generator, \
                    patch("httpx.Client.get", side_effect=AssertionError("No stock request expected")):
                app = create_app(mode=mode, cache_dir=Path(temp), clock=lambda:self.now)
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"X-Arcade":"1"}) as player:
                    state = (await player.post("/api/game")).json()
                    notice = state["notice"]
                    self.assertTrue(state["synthetic"])
                    if mode == "auto":
                        self.assertIn("fallback", notice)
                    for index, data in enumerate(originals):
                        self.assertEqual(state["chart"], indexed(data.bars[:60], data.bars[0].close))
                        self.assertEqual(state["label"], f"ASSET {chr(65 + index)}")
                        rid = state["round_id"]
                        await player.post("/api/ready", json={"round_id":rid})
                        state = (await player.post("/api/predict", json={"round_id":rid, "choice":"UP"})).json()
                        self.assertEqual(state["result"]["future"], indexed(data.bars[60:], data.bars[0].close, 1))
                        if index < 2:
                            state = (await player.post("/api/next", json={"round_id":rid})).json()
                    self.assertTrue(state["complete"])
                    fresh = (await player.post("/api/game")).json()
                    self.assertEqual(fresh["notice"], notice)
                    self.assertEqual(fresh["chart"], indexed(replay[0].bars[:60], replay[0].bars[0].close))
                    self.assertNotEqual(fresh["chart"], indexed(originals[0].bars[:60], originals[0].bars[0].close))
                    self.assertEqual(fresh["score"], 0)
                    self.assertIsNone(fresh["result"])
                    # A different browser starts a game; it must not change this player's path.
                    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"X-Arcade":"1"}) as other:
                        newer = (await other.post("/api/game")).json()
                        self.assertEqual(newer["chart"], indexed(other_game[0].bars[:60], other_game[0].bars[0].close))
                    restored = (await player.get("/api/game")).json()
                    self.assertEqual(restored["chart"], fresh["chart"])
                    rid = restored["round_id"]
                    await player.post("/api/ready", json={"round_id":rid})
                    result = (await player.post("/api/predict", json={"round_id":rid, "choice":"DOWN"})).json()["result"]
                    self.assertEqual(result["future"], indexed(replay[0].bars[60:], replay[0].bars[0].close, 1))
                initial_generator.assert_called_once_with()
                self.assertEqual(replay_generator.call_count, 2)

    async def test_real_replay_randomizes_windows_without_reloading_stock(self):
        data = synthetic(seed=113)[0]
        bars = list(data.bars)
        while len(bars) < 100:
            bars.append(replace(bars[-1], date=(date.fromisoformat(bars[-1].date) + timedelta(days=1)).isoformat()))
        real = replace(data, source="Alpha Vantage", symbol="PRIVATE-TICKER", bars=tuple(bars))
        loader = Mock(return_value=((real,), "REAL CACHED DATA"))
        app = create_app(loader=loader, clock=lambda:self.now)
        generators = [random.Random(1), random.Random(2)]
        with patch("arcade.game.random.Random", side_effect=generators), \
                patch("arcade.server.synthetic", side_effect=AssertionError("Real mode must stay real")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"X-Arcade":"1"}) as player:
                first = (await player.post("/api/game")).json()
                second = (await player.post("/api/game")).json()
        self.assertNotEqual(first["chart"], second["chart"])
        self.assertFalse(second["synthetic"])
        self.assertNotIn(real.symbol, str(second))
        loader.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
