import asyncio
import unittest

import httpx

from arcade.analyst import Analyst
from arcade.data import synthetic
from arcade.server import create_app
from test_analyst import response_body


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 1000.0
        self.loads = 0
        def loader():
            self.loads += 1
            return synthetic(), "SYNTHETIC DEMO"
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
            app = create_app(loader=lambda: (synthetic(), "SYNTHETIC DEMO"), analyst=advisor, clock=lambda:self.now)
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
                release.set()
                self.assertEqual((await pending).status_code, 200)


if __name__ == "__main__":
    unittest.main()
