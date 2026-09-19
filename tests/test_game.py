from dataclasses import replace
import json
import unittest

from arcade.data import synthetic
from arcade.game import Game, GameError, evidence, outcome


class GameTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.game = Game.create(synthetic(), "SYNTHETIC DEMO", clock=lambda: self.now)

    def test_exact_thresholds(self):
        for end, expected in ((99, "FLAT"), (101, "FLAT"), (98.9999, "DOWN"), (101.0001, "UP")):
            self.assertEqual(outcome(100, end)[0], expected)

    def test_research_boundary(self):
        public = self.game.public()
        self.assertEqual(len(public["chart"]), 60)
        self.assertEqual([b["day"] for b in public["chart"]], list(range(-59, 1)))
        encoded = json.dumps(public)
        for secret in ("FICTION-1", "2000-", '"future"', '"answer"', '"date"'):
            self.assertNotIn(secret, encoded)
        self.assertIsNone(public["result"])
        r = self.game.round
        before = evidence(r.research)
        changed = r.data.bars[:60] + tuple(replace(b, close=b.close * 2) for b in r.future)
        r.data = replace(r.data, bars=changed)
        self.assertEqual(before, evidence(r.research))

    def test_ready_idempotent_and_no_early_reveal(self):
        self.now += 200
        self.assertEqual(self.game.public()["phase"], "ready")
        with self.assertRaises(GameError):
            self.game.predict(self.game.round.id, "UP")
        self.game.start(self.game.round.id)
        deadline = self.game.round.deadline
        self.now += 10
        self.game.start(self.game.round.id)
        self.assertEqual(self.game.round.deadline, deadline)
        self.assertIsNone(self.game.public()["result"])

    def test_correct_scoring_three_rounds(self):
        for number in range(3):
            r = self.game.round
            self.game.start(r.id)
            self.now += 6
            answer = outcome(r.research[-1].close, r.future[-1].close)[0]
            self.game.predict(r.id, answer)
            result = r.result
            self.assertEqual(result["accuracy"], 100)
            self.assertEqual(result["speed"], 18)
            self.assertEqual(result["combo_bonus"], number * 10)
            self.assertEqual(len(result["future"]), 5)
            score = self.game.score
            with self.assertRaises(GameError):
                self.game.predict(r.id, answer)
            self.assertEqual(self.game.score, score)
            if number < 2:
                self.game.advance(r.id)
                with self.assertRaises(GameError):
                    self.game.predict(r.id, "UP")
        self.assertTrue(self.game.public()["complete"])
        self.assertEqual(self.game.score, 384)
        with self.assertRaises(GameError):
            self.game.advance(self.game.round.id)

    def test_timeout_and_incorrect_reset_combo(self):
        self.game.combo = 2
        r = self.game.round
        self.game.start(r.id)
        self.now += 60
        with self.assertRaises(GameError):
            self.game.predict(r.id, "UP")
        self.assertEqual(r.result["choice"], "No call")
        self.assertEqual(self.game.score, 0)
        self.assertEqual(self.game.combo, 0)
        self.game.advance(r.id)
        r = self.game.round
        self.game.start(r.id)
        correct = outcome(r.research[-1].close, r.future[-1].close)[0]
        self.game.predict(r.id, "UP" if correct != "UP" else "DOWN")
        self.assertEqual(r.result["speed"], 0)
        self.assertEqual(r.result["points"], 0)

    def test_indicator_values_flat_and_unavailable(self):
        bars = tuple(replace(b, open=100, high=100, low=100, close=100, volume=0) for b in synthetic()[0].bars[:60])
        bank = evidence(bars)
        self.assertEqual(bank["return_59"]["value"], 0)
        self.assertEqual(bank["sma_50"]["value"], 100)
        self.assertEqual(bank["rsi"]["value"], 50)
        self.assertEqual(bank["volatility"]["value"], 0)
        self.assertIsNone(bank["volume_ratio"]["value"])
        self.assertIsNone(evidence(bars[:10])["sma_20"]["value"])


if __name__ == "__main__":
    unittest.main()
