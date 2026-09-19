from dataclasses import replace
from datetime import date, timedelta
import json
import unittest

from arcade.data import synthetic
from arcade.game import Game, GameError, evidence, indexed, outcome


class GameTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.game = Game.create(synthetic(seed=113), "SYNTHETIC DEMO", clock=lambda: self.now)

    def test_exact_thresholds(self):
        for end, expected in ((99, "FLAT"), (101, "FLAT"), (98.9999, "DOWN"), (101.0001, "UP")):
            self.assertEqual(outcome(100, end)[0], expected)

    def test_research_boundary(self):
        public = self.game.public()
        self.assertEqual(len(public["chart"]), 60)
        self.assertEqual([b["day"] for b in public["chart"]], list(range(-59, 1)))
        encoded = json.dumps(public)
        for secret in (self.game.round.data.symbol, "2000-", '"future"', '"answer"', '"date"'):
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
        bars = tuple(replace(b, open=100, high=100, low=100, close=100, volume=0) for b in synthetic(seed=113)[0].bars[:60])
        bank = evidence(bars)
        self.assertEqual(bank["return_59"]["value"], 0)
        self.assertEqual(bank["sma_50"]["value"], 100)
        self.assertEqual(bank["rsi"]["value"], 50)
        self.assertEqual(bank["volatility"]["value"], 0)
        self.assertIsNone(bank["volume_ratio"]["value"])
        self.assertIsNone(evidence(bars[:10])["sma_20"]["value"])

    def test_summary_retains_best_combo_after_timeout(self):
        for _ in range(2):
            r = self.game.round
            self.game.start(r.id)
            self.game.predict(r.id, outcome(r.research[-1].close, r.future[-1].close)[0])
            self.game.advance(r.id)
        self.game.start(self.game.round.id)
        self.now += 60
        final = self.game.public()
        self.assertTrue(final["complete"])
        self.assertEqual(final["combo"], 0)
        self.assertEqual(final["summary"], {
            "correct_predictions": 2, "best_combo": 2, "analyst_questions": 0})
        self.assertEqual(final["result"]["choice"], "No call")

    def test_all_outcomes_fixed_before_choices_and_shared_with_research(self):
        datasets = synthetic(seed=909)
        future_snapshots = [data.bars[60:] for data in datasets]
        expected = [outcome(data.bars[59].close, data.bars[64].close) for data in datasets]
        for choice in ("DOWN", "FLAT", "UP", None):
            now = [1000.0]
            game = Game.create(datasets, "SYNTHETIC DEMO", clock=lambda: now[0])
            for index, data in enumerate(datasets):
                r = game.round
                self.assertIs(r.data, data)
                self.assertEqual(r.future, future_snapshots[index])
                before = game.public()
                self.assertEqual(before["label"], f"ASSET {chr(65 + index)}")
                self.assertEqual(before["evidence"], evidence(data.bars[:60]))
                self.assertEqual(before["chart"], indexed(data.bars[:60], data.bars[0].close))
                self.assertIsNone(before["result"])
                game.start(r.id)
                if choice is None:
                    now[0] += 60
                    game.expire()
                else:
                    game.predict(r.id, choice)
                self.assertEqual((r.result["answer"], r.result["change"]), expected[index])
                self.assertEqual(r.future, future_snapshots[index])
                self.assertEqual(r.result["future"], indexed(future_snapshots[index], data.bars[0].close, 1))
                if index < 2:
                    game.advance(r.id)

    def test_real_window_selection_random_seeded_and_leak_safe(self):
        data = synthetic(seed=113)[0]
        bars = list(data.bars)
        while len(bars) < 100:
            bars.append(replace(bars[-1], date=(date.fromisoformat(bars[-1].date) + timedelta(days=1)).isoformat()))
        real = replace(data, source="Alpha Vantage", symbol="PRIVATE-TICKER", bars=tuple(bars))
        def cutoffs(seed):
            return tuple(r.cutoff for r in Game.create((real,), "REAL CACHED DATA", seed=seed).rounds)
        self.assertEqual(cutoffs(42), cutoffs(42))
        self.assertGreater(len({cutoffs(seed) for seed in range(10)}), 1)
        for seed in range(10):
            a, b, c = cutoffs(seed)
            self.assertGreaterEqual(b - a, 5)
            self.assertGreaterEqual(c - b, 5)
        game = Game.create((real,), "REAL CACHED DATA", seed=42)
        self.assertNotIn(real.symbol, json.dumps(game.public()))
        self.assertTrue(all(r.data is real for r in game.rounds))


if __name__ == "__main__":
    unittest.main()
