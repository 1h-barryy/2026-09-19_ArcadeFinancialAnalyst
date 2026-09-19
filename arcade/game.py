"""Pure historical calculations and authoritative in-memory game state."""
from dataclasses import dataclass, field
from decimal import Decimal
import math
import random
import statistics
import time
import uuid

from .data import Bar, DataError, Dataset, scenario_windows


class GameError(ValueError):
    pass


def outcome(start: float, end: float) -> tuple[str, float]:
    change = (Decimal(str(end)) / Decimal(str(start)) - 1) * 100
    return ("DOWN" if change < -1 else "UP" if change > 1 else "FLAT", float(change))


def indexed(bars: tuple[Bar, ...], base: float, first_day: int = -59) -> list[dict]:
    return [{"day": first_day + i, "open": b.open / base * 100,
             "high": b.high / base * 100, "low": b.low / base * 100,
             "close": b.close / base * 100, "volume": b.volume} for i, b in enumerate(bars)]


def evidence(bars: tuple[Bar, ...]) -> dict:
    """Receives the research slice ONLY. All indicators end at day zero."""
    closes = [b.close for b in bars]
    base, last = closes[0], closes[-1]
    bank = {}

    def add(key, label, value, unit, explanation):
        bank[key] = {"label": label, "value": None if value is None else round(value, 4),
                     "unit": unit, "explanation": explanation}

    for lag in (1, 5, 20, 59):
        value = (last / closes[-lag - 1] - 1) * 100 if len(closes) > lag else None
        add(f"return_{lag}", f"{lag}-session return", value, "%",
            "Historical close-to-close price change; it does not predict the hidden outcome.")
    add("last", "Last indexed close", last / base * 100, "index", "The first visible closing price is indexed to 100.")
    for period in (10, 20, 50):
        average = statistics.mean(closes[-period:]) if len(closes) >= period else None
        add(f"sma_{period}", f"SMA {period}", None if average is None else average / base * 100,
            "index", "A simple moving average smooths past closes and lags changes.")
        add(f"gap_{period}", f"Close vs SMA {period}", None if average is None else (last / average - 1) * 100,
            "%", "Positive means the last close is above this historical average; negative means below.")
    rsi = None
    if len(closes) >= 15:
        differences = [b - a for a, b in zip(closes, closes[1:])]
        gain = statistics.mean(max(d, 0) for d in differences[:14])
        loss = statistics.mean(max(-d, 0) for d in differences[:14])
        for d in differences[14:]:
            gain, loss = (gain * 13 + max(d, 0)) / 14, (loss * 13 + max(-d, 0)) / 14
        rsi = 50 if gain == loss == 0 else 100 if loss == 0 else 100 - 100 / (1 + gain / loss)
    add("rsi", "RSI 14 (Wilder)", rsi, "", "Momentum oscillator, not a reversal guarantee; initialized within the visible window.")
    returns = [b / a - 1 for a, b in zip(closes, closes[1:])]
    volatility = statistics.stdev(returns[-20:]) * math.sqrt(252) * 100 if len(returns) >= 20 else None
    add("volatility", "20-session annualized volatility", volatility, "%",
        "Sample standard deviation of daily simple returns, annualized with 252 sessions. Measures dispersion, not direction.")
    mean_volume = statistics.mean(b.volume for b in bars[-21:-1]) if len(bars) >= 21 else 0
    add("volume_ratio", "Last volume / prior 20-session mean", bars[-1].volume / mean_volume if mean_volume else None,
        "×", "Compares the last session with the preceding sessions, excluding the last session from the baseline.")
    add("volume", "Last session volume", bars[-1].volume, "shares", "Reported share volume for the last visible session.")
    return bank


def insights(bank: dict) -> dict[str, str]:
    fast, slow = bank["return_5"]["value"], bank["return_20"]["value"]
    conflicting = fast is not None and slow is not None and fast * slow < 0
    return {
        "momentum": "Recent and longer-window returns point in different directions." if conflicting else
                    "Recent and longer-window returns do not have opposing signs; agreement is not predictive certainty.",
        "trend": "Compare the last indexed close with the moving averages; averages describe past prices and react with a delay.",
        "risk": "Large historical fluctuations widen uncertainty; volatility alone cannot tell you the next direction.",
        "volume": "Higher relative volume indicates more activity, but volume alone does not establish buying or selling pressure.",
        "rsi": "Extreme momentum readings can persist. RSI alone is not evidence that a reversal must occur.",
    }


@dataclass
class Round:
    data: Dataset
    cutoff: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    deadline: float | None = None
    result: dict | None = None
    history: list = field(default_factory=list)
    asking: bool = False

    @property
    def research(self):
        return self.data.bars[self.cutoff - 59:self.cutoff + 1]

    @property
    def future(self):
        return self.data.bars[self.cutoff + 1:self.cutoff + 6]


@dataclass
class Game:
    rounds: list[Round]
    notice: str
    current: int = 0
    score: int = 0
    combo: int = 0
    analyst_questions: int = 0
    clock: object = time.monotonic

    @classmethod
    def create(cls, datasets: tuple[Dataset, ...], notice: str, clock=time.monotonic, *, seed: int | None = None):
        if len(datasets) == 3 and all(d.source == "SYNTHETIC DEMO" for d in datasets):
            rounds = [Round(d, 59) for d in datasets]
        else:
            data = datasets[0]
            candidates = scenario_windows(data)
            if not candidates:
                raise DataError("Three usable windows with non-overlapping five-session outcomes are required.")
            # Chronological cutoffs ensure an earlier reveal never exposes a later round's outcome.
            ends = random.Random(seed).choice(candidates)
            rounds = [Round(data, end) for end in ends]
        return cls(rounds, notice, clock=clock)

    @property
    def round(self):
        return self.rounds[self.current]

    def check_id(self, round_id):
        if round_id != self.round.id:
            raise GameError("That round is no longer current.")

    def expire(self):
        r = self.round
        if r.result is None and r.deadline is not None and self.clock() >= r.deadline:
            self.finish(None)

    def start(self, round_id):
        self.check_id(round_id)
        if self.round.deadline is None:
            self.round.deadline = self.clock() + 60
        self.expire()

    def finish(self, choice):
        r = self.round
        correct_answer, change = outcome(r.research[-1].close, r.future[-1].close)
        correct = choice == correct_answer
        remaining = max(0, r.deadline - self.clock()) if r.deadline is not None else 0
        self.combo = self.combo + 1 if correct else 0
        accuracy = 100 if correct else 0
        speed = min(20, math.floor(remaining / 3)) if correct else 0
        combo_bonus = 10 * (self.combo - 1) if correct else 0
        points = accuracy + speed + combo_bonus
        self.score += points
        r.result = {"choice": choice or "No call", "answer": correct_answer, "change": change,
                    "correct": correct, "points": points, "accuracy": accuracy,
                    "speed": speed, "combo_bonus": combo_bonus, "symbol": r.data.symbol,
                    "start_date": r.research[0].date, "cutoff_date": r.research[-1].date,
                    "end_date": r.future[-1].date, "price_basis": r.data.price_basis,
                    "downloaded_at": r.data.downloaded_at,
                    "future": indexed(r.future, r.research[0].close, 1)}

    def predict(self, round_id, choice):
        self.check_id(round_id)
        if choice not in ("DOWN", "FLAT", "UP"):
            raise GameError("Choose DOWN, FLAT or UP.")
        self.expire()
        if self.round.result is not None:
            raise GameError("Prediction rejected: this round is already closed (submitted or timed out).")
        if self.round.deadline is None:
            raise GameError("Wait until the chart is ready.")
        self.finish(choice)

    def advance(self, round_id):
        self.check_id(round_id)
        self.expire()
        if self.round.result is None:
            raise GameError("Finish the current round first.")
        if self.current >= 2:
            raise GameError("Game complete. Start a new game.")
        self.current += 1

    def public(self):
        self.expire()
        r = self.round
        correct_predictions = best_combo = streak = 0
        for round_ in self.rounds:
            if round_.result is not None:
                correct = round_.result["correct"]
                correct_predictions += int(correct)
                streak = streak + 1 if correct else 0
                best_combo = max(best_combo, streak)
        return {"round_id": r.id, "round": self.current + 1, "total_rounds": 3,
                "score": self.score, "combo": self.combo, "notice": self.notice,
                "synthetic": r.data.source == "SYNTHETIC DEMO",
                "label": f"ASSET {chr(65 + self.current)}", "source": r.data.source,
                "phase": "result" if r.result else "research" if r.deadline is not None else "ready",
                "remaining": max(0, r.deadline - self.clock()) if r.deadline is not None else 60,
                "chart": indexed(r.research, r.research[0].close), "evidence": evidence(r.research),
                "result": r.result, "complete": self.current == 2 and r.result is not None,
                "history": r.history, "asking": r.asking,
                "summary": {"correct_predictions": correct_predictions,
                            "best_combo": best_combo, "analyst_questions": self.analyst_questions}}
