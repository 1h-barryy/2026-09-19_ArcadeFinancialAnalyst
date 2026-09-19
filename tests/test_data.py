from dataclasses import asdict, replace
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from arcade.data import (DataError, candidate_windows, download, load, read_cache,
                         synthetic, ticker, validate, write_cache)


def provider_payload():
    return {"Meta Data": {"2. Symbol": "IBM"}, "Time Series (Daily)": {
        b.date: {f"{i}. {name}": str(getattr(b, name)) for i, name in
                 enumerate(("open", "high", "low", "close", "volume"), 1)}
        for b in reversed(synthetic()[0].bars)}}


class DataTests(unittest.TestCase):
    def client(self, payload=None, status=200, failure=None, text=None):
        def handler(request):
            if failure:
                raise failure("redacted", request=request)
            self.assertEqual(request.url.params["function"], "TIME_SERIES_DAILY")
            self.assertEqual(request.url.params["outputsize"], "compact")
            return httpx.Response(status, json=payload) if text is None else httpx.Response(status, text=text)
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_inputs(self):
        for value in ("", " ", "../key", "a?apikey=x", "X" * 21, "IBM..", "A-", "A B"):
            with self.subTest(value=value), self.assertRaises(DataError):
                ticker(value)
        self.assertEqual(ticker(" brk.b "), "BRK.B")
        with self.assertRaisesRegex(DataError, "key missing"):
            download("IBM", "")

    def test_response_normalization_and_metadata(self):
        data = download("IBM", "mock-only", self.client(provider_payload()))
        self.assertEqual(len(data.bars), 65)
        self.assertEqual(data.source, "Alpha Vantage")
        self.assertIn("not split", data.price_basis)
        self.assertLess(data.bars[0].date, data.bars[-1].date)

    def test_failures_are_safe(self):
        cases = [self.client({}, 500), self.client({}, 429), self.client(text="bad JSON"),
                 self.client({"Error Message": "secret-provider-body"}),
                 self.client({"Note": "secret-provider-body"}), self.client({"Information": "private"}),
                 self.client({}), self.client([]), self.client(failure=httpx.ReadTimeout),
                 self.client(failure=httpx.ConnectError)]
        for client in cases:
            with self.subTest(client=client), self.assertRaises(DataError) as caught:
                download("IBM", "do-not-expose", client)
            self.assertNotIn("do-not-expose", str(caught.exception))
            self.assertNotIn("secret-provider-body", str(caught.exception))

    def test_validation(self):
        valid = [asdict(b) for b in synthetic()[0].bars]
        bads = [[], valid[:64], list(reversed(valid)), [valid[0]] + valid[:-1]]
        for field, value in (("close", float("nan")), ("open", -1), ("high", 0),
                             ("volume", 1.2), ("volume", True), ("date", "nonsense")):
            rows = [dict(b) for b in valid]
            rows[0][field] = value
            bads.append(rows)
        for rows in bads:
            with self.subTest(rows=len(rows)), self.assertRaises(DataError):
                validate(rows)

    def test_duplicate_json_and_wrong_symbol(self):
        with self.assertRaises(DataError):
            download("IBM", "mock", self.client(text='{"x":1,"x":2}'))
        with self.assertRaises(DataError):
            download("AAPL", "mock", self.client(provider_payload()))

    def test_modes_cache_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch("arcade.data.download", side_effect=AssertionError("no network")):
                datasets, notice = load("demo", "IBM", "", directory)
                self.assertEqual(datasets, synthetic())
                self.assertIn("SYNTHETIC DEMO", notice)
            datasets, notice = load("auto", "IBM", "", directory)
            self.assertIn("fallback", notice)
            with self.assertRaises(DataError):
                load("live", "IBM", "", directory)
            real = download("IBM", "mock", self.client(provider_payload()))
            write_cache(directory / "IBM.json", real)
            self.assertEqual(read_cache(directory / "IBM.json", "IBM"), real)
            (directory / "IBM.json").write_text("bad", encoding="utf-8")
            self.assertIn("cache", load("auto", "IBM", "", directory)[1])

    def test_synthetic_fixed_and_varied(self):
        a, b = synthetic(), synthetic()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        self.assertEqual(len({round(d.bars[-1].close / d.bars[59].close, 4) for d in a}), 3)
        self.assertTrue(all(candidate_windows(d) for d in a))

    def test_successful_live_cache_reuse_and_write_failure(self):
        raw = download("IBM", "mock", self.client(provider_payload()))
        bars = list(raw.bars)
        for i in range(35):
            bars.append(replace(bars[-1], date=(date.fromisoformat(bars[-1].date) + timedelta(days=1)).isoformat()))
        real = replace(raw, bars=tuple(bars))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with patch("arcade.data.download", return_value=real) as request:
                result, notice = load("live", "IBM", "mock", folder)
                self.assertIn("succeeded", notice)
                self.assertEqual(result, (real,))
                request.assert_called_once()
            with patch("arcade.data.download", side_effect=AssertionError("cache must prevent request")):
                result, notice = load("auto", "IBM", "", folder)
                self.assertIn("CACHED", notice)
                self.assertEqual(result, (real,))
            with patch("arcade.data.download", return_value=real), patch("arcade.data.write_cache", side_effect=PermissionError):
                result, notice = load("live", "IBM", "mock", folder)
                self.assertEqual(result, (real,))
                self.assertIn("could not be saved", notice)

    def test_split_screen_and_short_real_history(self):
        original = synthetic()[0]
        bars = list(original.bars)
        for i in range(30,65):
            bars[i] = replace(bars[i], open=bars[i].open/2, high=bars[i].high/2, low=bars[i].low/2, close=bars[i].close/2)
        self.assertEqual(candidate_windows(replace(original,bars=tuple(bars))), [])
        real = download("IBM", "mock", self.client(provider_payload()))
        with tempfile.TemporaryDirectory() as temp, patch("arcade.data.download", return_value=real):
            with self.assertRaisesRegex(DataError,"usable real windows"):
                load("live", "IBM", "mock", Path(temp))
            self.assertIn("SYNTHETIC DEMO fallback", load("auto", "IBM", "mock", Path(temp))[1])


if __name__ == "__main__":
    unittest.main()
