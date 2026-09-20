# Arcade Financial Analyst

A short Wall Street-style stock prediction game built around API communication.

The player gets **3 rounds**. In each round, you have **60 seconds** to study historical market data, ask an AI analyst questions, and predict the next market move:

**DOWN / FLAT / UP**

After making a call, the next 5 trading sessions are revealed and the player earns points based on accuracy, speed, and combo.

The game runs locally in a browser with a Python backend.

---

## Demo

> Demo video: add link here

### Main Features

- 3-round stock prediction game
- 60-second research timer
- Candlestick / K-line and line chart views
- Volume and technical indicators
- OpenAI-powered analyst chat
- Randomized scenarios on replay
- Alpha Vantage support for real historical stock data
- Anonymous stock identity during research
- Accuracy, speed, and combo scoring
- Start screen, round reveals, final score, and replay

The AI analyst explains the available evidence but does **not** choose UP, DOWN, or FLAT for the player.

---

## Quick Start

Requires **Python 3.11+**.

Clone the repository and open PowerShell in the project folder.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --mode demo

## API Keys 

Private API keys are intentionally not included in this repository.

The game can be launched immediately in `demo` mode without a stock API key:

```powershell
.\.venv\Scripts\python.exe run.py --mode demo