r"""Run from PowerShell: .venv\Scripts\python.exe run.py --mode demo."""
import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

from arcade.data import DataError, ticker
from arcade.server import create_app


def main():
    parser = argparse.ArgumentParser(description="Arcade financial analyst — local historical prediction game")
    parser.add_argument("--mode", choices=("live", "auto", "demo"), default="auto")
    parser.add_argument("--ticker", default="IBM", help="Alpha Vantage symbol, hidden during research")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        symbol = ticker(args.ticker)
    except DataError as exc:
        parser.error(str(exc))
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535.")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    # HTTP libraries must not log query-string credentials, even on failed requests.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).disabled = True
    app = create_app(args.mode, symbol, os.getenv("ALPHAVANTAGE_API_KEY", ""),
                     os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_MODEL") or "gpt-4.1-mini")
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
