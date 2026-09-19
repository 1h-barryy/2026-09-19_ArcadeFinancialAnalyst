"""Provider boundary, validated OHLCV format, private cache and fictional data."""
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
import json
import math
from pathlib import Path
import random
import re

import httpx


class DataError(ValueError):
    """Safe user-facing error; never includes provider bodies or request URLs."""


def ticker(value: str) -> str:
    if (not isinstance(value, str) or len(value.strip()) > 20
            or not re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", value.strip())):
        raise DataError("Invalid ticker: use 1–20 letters, digits, dots or hyphens.")
    return value.strip().upper()


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class Dataset:
    bars: tuple[Bar, ...]
    source: str
    symbol: str
    downloaded_at: str
    price_basis: str


def validate(rows: list[dict], minimum: int = 65) -> tuple[Bar, ...]:
    if not isinstance(rows, list) or len(rows) < minimum:
        raise DataError(f"Insufficient history: at least {minimum} trading sessions are required.")
    result = []
    previous = ""
    try:
        for row in rows:
            day = row["date"]
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or day <= previous:
                raise ValueError()
            values = [row[k] for k in ("open", "high", "low", "close", "volume")]
            if any(isinstance(v, bool) for v in values):
                raise ValueError()
            o, h, low, c, v = map(float, values)
            if not all(math.isfinite(x) for x in (o, h, low, c, v)):
                raise ValueError()
            if min(o, h, low, c) <= 0 or v < 0 or not v.is_integer():
                raise ValueError()
            if not low <= min(o, c) <= max(o, c) <= h:
                raise ValueError()
            result.append(Bar(day, o, h, low, c, int(v)))
            previous = day
    except (KeyError, TypeError, ValueError, OverflowError):
        raise DataError("Malformed OHLCV: check dates, ordering, duplicates, finite prices, volume and high/low bounds.") from None
    return tuple(result)


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON key")
        obj[key] = value
    return obj


def download(symbol: str, key: str, client: httpx.Client | None = None) -> Dataset:
    symbol = ticker(symbol)
    if not key.strip():
        raise DataError("Alpha Vantage key missing. Enter ALPHAVANTAGE_API_KEY in the private .env file.")
    if client is None:
        with httpx.Client(timeout=15, follow_redirects=False) as owned:
            return download(symbol, key, owned)
    try:
        response = client.get("https://www.alphavantage.co/query", params={
            "function": "TIME_SERIES_DAILY", "symbol": symbol,
            "outputsize": "compact", "datatype": "json", "apikey": key,
        })
        if response.status_code == 429:
            raise DataError("Alpha Vantage rate limit reached. Reuse cache or try later.")
        if response.status_code != 200:
            raise DataError(f"Alpha Vantage HTTP failure ({response.status_code}).")
        payload = json.loads(response.text, object_pairs_hook=unique_object)
    except httpx.TimeoutException:
        raise DataError("Alpha Vantage request timed out. Try again later or use demo mode.") from None
    except httpx.RequestError:
        raise DataError("Alpha Vantage network failure. Check your connection or use demo mode.") from None
    except (ValueError, UnicodeError):
        raise DataError("Alpha Vantage returned invalid JSON.") from None
    if not isinstance(payload, dict):
        raise DataError("Alpha Vantage returned an unexpected response.")
    if "Error Message" in payload:
        raise DataError("Alpha Vantage rejected the ticker or request. Check the configured ticker.")
    if "Note" in payload or "Information" in payload:
        raise DataError("Alpha Vantage reports a rate limit or access restriction. Check your free key and try later.")
    try:
        if payload["Meta Data"]["2. Symbol"].upper() != symbol:
            raise DataError("Alpha Vantage returned a different symbol; data rejected.")
        series = payload["Time Series (Daily)"]
        rows = [{"date": day, **{name: values[f"{i}. {name}"] for i, name in
                enumerate(("open", "high", "low", "close", "volume"), 1)}}
                for day, values in sorted(series.items())]
    except (KeyError, TypeError, AttributeError):
        raise DataError("Alpha Vantage returned empty or incomplete daily data.") from None
    return Dataset(validate(rows), "Alpha Vantage", symbol,
                   datetime.now(timezone.utc).isoformat(), "raw/as-traded; not split or dividend adjusted")


def read_cache(path: Path, symbol: str) -> Dataset:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        if obj["source"] != "Alpha Vantage" or obj["symbol"] != symbol:
            raise ValueError()
        if obj["price_basis"] != "raw/as-traded; not split or dividend adjusted":
            raise ValueError()
        if datetime.fromisoformat(obj["downloaded_at"]).tzinfo is None:
            raise ValueError()
        return Dataset(validate(obj["bars"]), obj["source"], symbol, obj["downloaded_at"], obj["price_basis"])
    except (OSError, ValueError, KeyError, TypeError):
        raise DataError("Local stock cache is unreadable or invalid; a fresh download is needed.") from None


def write_cache(path: Path, data: Dataset) -> None:
    # Atomic replacement: a failed write cannot turn a previous good cache into partial JSON.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(data), allow_nan=False), encoding="utf-8")
    temporary.replace(path)


SYNTHETIC_PATTERNS = (
    "uptrend", "downtrend", "sideways", "choppy", "high_volatility",
    "reversal_up", "reversal_down", "breakout",
)


def _synthetic_scenario(pattern: str, rng: random.Random) -> Dataset:
    """Generate all 65 sessions with the same process on both sides of the cutoff."""
    rows, price, day = [], rng.uniform(60, 180), date(2000, 1, 3)
    anchor = price
    trend = rng.uniform(0.001, 0.004)
    volatility = rng.uniform(0.006, 0.015)
    pivot = rng.randint(23, 47)
    direction = rng.choice((-1, 1))
    base_volume = rng.randint(400_000, 2_500_000)
    for i in range(65):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        sigma = volatility
        if pattern == "uptrend":
            drift = trend
        elif pattern == "downtrend":
            drift = -trend
        elif pattern == "sideways":
            sigma *= 0.55
            drift = 0.10 * math.log(anchor / price)
        elif pattern == "choppy":
            sigma *= 1.2
            drift = 0.006 * math.sin(i * 0.7) + 0.06 * math.log(anchor / price)
        elif pattern == "high_volatility":
            sigma *= 2.5
            drift = direction * trend * 0.25
        elif pattern in ("reversal_up", "reversal_down"):
            drift = trend * (1 if i >= pivot else -1)
            if pattern == "reversal_down":
                drift = -drift
        else:  # Breakout from a quieter range, in either direction.
            sigma *= 0.5 if i < pivot else 1.4
            drift = 0.08 * math.log(anchor / price) if i < pivot else direction * trend * 1.6
        o = price * math.exp(max(-0.03, min(0.03, rng.gauss(0, sigma * 0.2))))
        change = max(-0.12, min(0.12, rng.gauss(drift, sigma)))
        price = o * math.exp(change)
        wick = rng.uniform(0.001, sigma * 0.8 + 0.002)
        rows.append(dict(date=day.isoformat(), open=o, high=max(o, price) * math.exp(wick),
                         low=min(o, price) * math.exp(-wick), close=price,
                         volume=int(base_volume * rng.uniform(0.6, 1.4) * (1 + abs(change) / sigma * 0.25))))
        day += timedelta(days=1)
    return Dataset(validate(rows), "SYNTHETIC DEMO", f"FICTION-{rng.getrandbits(48):012X}",
                   "2000-01-01T00:00:00+00:00", "fictional raw prices")


def synthetic(seed: int | None = None) -> tuple[Dataset, ...]:
    """Fresh entropy by default; an explicit seed reproduces the complete datasets."""
    rng = random.Random(seed)
    scenarios, seen = [], set()
    # Entire paths are generated before gameplay; player choices never enter this function.
    for pattern in rng.sample(SYNTHETIC_PATTERNS, 3):
        data = _synthetic_scenario(pattern, rng)
        while data.bars in seen:
            data = _synthetic_scenario(pattern, rng)
        seen.add(data.bars)
        scenarios.append(data)
    return tuple(scenarios)


def candidate_windows(data: Dataset) -> list[int]:
    """Review every full research + outcome window for suspicious raw-price discontinuities."""
    candidates = []
    for end in range(59, len(data.bars) - 5):
        window = data.bars[end - 59:end + 6]
        if all(abs(b.open / a.close - 1) < 0.18 and abs(b.close / a.close - 1) < 0.18
               for a, b in zip(window, window[1:])):
            candidates.append(end)
    return candidates


def scenario_windows(data: Dataset) -> list[tuple[int, int, int]]:
    """Unique chronological cutoffs whose hidden five-session intervals do not overlap."""
    return [(a, b, c) for a, b, c in combinations(candidate_windows(data), 3)
            if b - a >= 5 and c - b >= 5]


def load(mode: str, symbol: str, key: str, cache_dir: Path,
         client: httpx.Client | None = None) -> tuple[tuple[Dataset, ...], str]:
    symbol = ticker(symbol)
    if mode not in ("live", "auto", "demo"):
        raise DataError("Stock mode must be live, auto or demo.")
    if mode == "demo":
        return synthetic(), "SYNTHETIC DEMO · Fictional data. No stock API request was made."
    path = cache_dir / f"{symbol}.json"
    notes = []
    if mode == "auto" and path.exists():
        try:
            cached = read_cache(path, symbol)
            if not scenario_windows(cached):
                raise DataError("Cached data has too few usable windows after raw-price screening.")
            return (cached,), "REAL CACHED DATA · Reused validated local data; no new stock request."
        except DataError as exc:
            notes.append(str(exc))
    try:
        data = download(symbol, key, client)
        try:
            write_cache(path, data)
        except OSError:
            notes.append("Download succeeded, but the local cache could not be saved.")
        if not scenario_windows(data):
            raise DataError("Too few usable real windows after raw-price split/jump screening; choose another ticker.")
        return (data,), " ".join(notes + ["REAL LIVE DATA · Alpha Vantage request succeeded."])
    except DataError as exc:
        if mode == "live":
            raise
        return synthetic(), " ".join(notes + [str(exc), "SYNTHETIC DEMO fallback · Fictional data; real stock loading failed."])
