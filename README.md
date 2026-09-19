# Arcade financial analyst

A short local stock prediction game: **3 rounds, 60 visible trading sessions, 60 seconds of research, and a 5-session reveal**. Python handles stock API communication, calculations, the OpenAI analyst, deadlines and scoring. The browser is a small dark trading terminal, not a trading simulator.

## Current status

- Implemented: Alpha Vantage adapter, strict OHLCV validation, private disk cache, explicit live/auto/demo modes, randomized fictional scenarios with reproducible test seeds, Python indicators, bounded OpenAI Responses requests, and the complete three-round browser game.
- Verified locally on Windows with Python 3.14.3: **35 automated tests passed**, including randomized scenarios and replay, and Python compilation passed. Earlier Chrome checks covered the start screen, LINE/CANDLE switching, research, commitments, reveals, timeout, final statistics and replay. The Analyst Desk presentation was also checked with explicitly labeled mocked responses. No external calls occur in the test suite.
- **Alpha Vantage live connection: UNVERIFIED. OpenAI live connection: UNVERIFIED.** Both credentials were absent during implementation. Successful provider responses and failures were mocked; synthetic data is not proof of a real connection.
- No services purchased, public deployment, database, accounts, trading, commits, pushes, uploads or assignment submissions were performed.

## Setup and run (PowerShell)

Run commands from this repository's root. Use Python 3.11 or newer; the installed environment was tested with 3.14.3. On this computer, the available launcher is `$HOME\.local\bin\python3.14.exe`; `python` and `py` were not on PATH during setup.

```powershell
# Create the environment only if it does not exist.
if (-not (Test-Path .venv\Scripts\python.exe)) {
    & "$HOME\.local\bin\python3.14.exe" -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --mode demo
```

Open **http://127.0.0.1:8000** in a browser. Stop the server with Ctrl+C. No activation or PowerShell execution-policy changes are needed. On another machine with the standard Python launcher, replace the environment-creation command with `py -3 -m venv .venv`.

```powershell
# Cache first, then stock API, with a clearly announced fictional fallback:
.\.venv\Scripts\python.exe run.py --mode auto --ticker IBM

# Real request required; loading fails visibly if it cannot succeed:
.\.venv\Scripts\python.exe run.py --mode live --ticker MSFT

# If port 8000 is occupied:
.\.venv\Scripts\python.exe run.py --mode demo --port 8001

# No provider network requests; temporary caches and mocked responses:
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The server binds only to `127.0.0.1`. Run one server worker. Games are in memory and disappear when the process stops. Refreshing the page restores the active browser session; its deadline does not restart. Separate browsers receive separate sessions. Up to 32 sessions are retained, with idle cleanup when a new game starts.

## Playing at the terminal

- The start screen shows the game title, three rounds and 60 seconds per round. Press **Start** to load the first round; the clock begins only after the chart is painted. Restoring an unstarted round does not automatically start its timer. An already-running round keeps its original deadline across refreshes.
- Switch **LINE / CANDLE** at any time. Candlesticks use the existing indexed open/high/low/close data, including wicks; volume stays below the price chart. Hover to inspect a session's indexed OHLC and share volume. Chart switching makes no API request. The future area stays empty until the backend authorizes a reveal.
- **AI Analyst Chat** uses distinct user/analyst message bubbles and role avatars, with verified numerical evidence in a separate attachment-style card. A high-contrast composer provides a message box, character count, suggested questions and a Send message button. Enter sends; Shift+Enter adds a line. The latest exchange stays in view from the question through the beginning of the reply; scroll within the conversation for longer evidence cards. Evidence validation and provider behavior are unchanged. Pending requests show your question while the countdown continues.
- After a call or timeout, the chart immediately adds the five authorized outcome sessions. The reveal shows your call, actual return, correct direction, and accuracy/speed/combo breakdown. Research uses anonymous labels; reveals use the existing real ticker or a clearly fictional demo identifier. The current dataset does not contain company names, so no extra company-lookup service is used.
- After the third reveal, choose **View shift summary** for the dedicated end screen: final score, correct predictions, best combo and analyst question count. **Review final round** returns to the last reveal. **Play Again** starts a fresh three-round game without reloading the page, resetting the score, combo, counters, conversations, chart selection and timer. Synthetic scenarios are newly generated; real rounds are randomly selected from the already loaded stock data.
- The question count measures valid nonblank submissions during research, including provider failures; duplicate outstanding requests, blank questions and closed-round requests do not count. It is independent of the six-message history limit. Best combo is retained even when a later miss or timeout resets the active combo.

## Private credentials

A **blank private `.env` was created after verifying that Git ignores it**. Enter keys locally in that file, after the equals signs:

```dotenv
ALPHAVANTAGE_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=
```

Do not paste keys into chat. Do not put keys in `.env.example`; that is the public, blank template. Never overwrite an existing `.env` to follow setup instructions. For a fresh clone, first verify `git check-ignore .env`, then copy `.env.example` to `.env` only if `.env` is absent. Restart the server after changing keys. Existing process environment variables take precedence over `.env`.

Get a free stock key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key). Set `OPENAI_API_KEY` to your personal OpenAI API key. Leave `OPENAI_MODEL` blank for `gpt-4.1-mini`, or supply a compatible inexpensive model with Responses structured-output support. Account access to that model still needs a successful request to verify.

Stock mode and analyst availability are independent: **demo mode can use a real OpenAI analyst**. With no OpenAI key the chart and game remain usable, and the analyst is visibly unavailable. Calls consume API credit only when the player submits a question. The app cannot inspect your remaining promotional credit or prevent account-level auto-recharge; check credit and billing settings locally before enabling the analyst to keep additional spending at $0. It does not purchase credits or upgrade services.

## Stock API and data contract

The adapter uses backend HTTPS GET to `https://www.alphavantage.co/query` with these documented parameters:

| Parameter | Value |
| --- | --- |
| `function` | `TIME_SERIES_DAILY` |
| `symbol` | Validated `--ticker` argument (default `IBM`) |
| `outputsize` | `compact` |
| `datatype` | `json` |
| `apikey` | Private `ALPHAVANTAGE_API_KEY` |

Official documentation checked on 2026-09-19: [daily data and parameters](https://www.alphavantage.co/documentation/#daily), [free-service limits](https://www.alphavantage.co/support/). Compact daily output returns up to 100 raw sessions and is available to free keys. Full daily history and the daily adjusted endpoint are premium; this app does not request either. The free service documents 25 requests per day; the provider's actual entitlement and rate notices remain authoritative.

Every validated bar contains `date`, `open`, `high`, `low`, `close`, `volume`. Dataset metadata contains `source`, `symbol`, UTC `downloaded_at`, and `price_basis`. Provider reverse chronology is explicitly normalized into ascending order, then validated. Duplicate JSON keys/dates, invalid date order, non-finite or non-positive prices, invalid volume, inconsistent OHLC, incomplete fields and fewer than 65 sessions are rejected. Three real rounds need at least 75 sessions and three usable screened windows with non-overlapping five-session outcome intervals. Missing sessions are never filled with invented prices.

| Mode | Behavior |
| --- | --- |
| `demo` | Generates three fresh randomized fictional scenarios per game without a stock request or stock credential. Persistent **SYNTHETIC DEMO** banner and `FICTION-*` identities. Explicit test seeds make generation reproducible. |
| `auto` | Reuses a validated usable real cache; otherwise tries the stock API. Any fallback explicitly explains the failure and labels data fictional. |
| `live` | Makes a real request on first game load in that server process. Failure stops loading; never silently substitutes demo data. |

Successful downloads are atomically cached under ignored `.local/cache/`. All real rounds and questions reuse the same loaded data. A new game randomly selects windows from the process's loaded real dataset; restart the server in live mode to deliberately request fresh data. Synthetic games generate new paths on every new game, including auto-mode fallback, while retaining the original fallback notice. Replay makes no additional stock API request. Auto caches have **no age expiration** because these are historical exercises, not current quotes. Download time is available after reveal. Failed live loads have a 60-second local cooldown. Cache-read errors are surfaced before trying the API; failed cache writes are announced while valid downloaded data remains playable.

Provider errors are categorized into missing key, rejected ticker/request, malformed or incomplete data, HTTP failure, rate/access notice, timeout and network failure. Raw provider bodies and full keyed URLs are never included in user messages or logs. HTTP client request logging is disabled by the launcher. Authentication stays on the backend; there are no third-party frontend scripts or API keys in browser assets.

## Historical boundary and calculations

Each round owns a fixed research slice and a separate fixed hidden slice on the backend. Research endpoints serialize **only 60 historical bars**, indexed OHLC (first visible close = 100), volume, relative days −59 through 0, and derived evidence. They exclude dates, ticker, future bars and the answer. The five hidden bars are returned only after an accepted prediction or server-authorized timeout. A result reveals the symbol and dates (fictional identifiers and dates for demo scenarios).

The browser paints the chart, then sends a ready acknowledgement. The server starts a 60-second monotonic deadline once; repeated ready requests cannot extend it. Polling reads state only, without model or stock requests. Expiration is enforced on the next backend interaction, including a prediction or regular state poll, even if the browser was suspended. Duplicate, stale-round and late predictions are rejected. The clock continues during analyst requests. Replay starts a fresh game, not a retry of an already committed prediction.

All indicators are calculated in Python using only the visible slice:

| Evidence | Definition |
| --- | --- |
| Returns | `(last close / close N sessions earlier − 1) × 100`, for N = 1, 5, 20, 59. |
| SMA 10 / 20 / 50 | Arithmetic mean of the last N closes; displayed on the same indexed-price scale. Close-to-SMA gaps are percentages. |
| RSI 14 | Wilder smoothing. Initial mean gains/losses over the first 14 changes; subsequent means use `(previous × 13 + change) / 14`. Flat/no gains or losses = 50; no losses with gains = 100. |
| Volatility | Sample standard deviation (`ddof=1`) of the last 20 simple daily returns, multiplied by `sqrt(252) × 100`. |
| Relative volume | Last volume divided by the mean of the preceding 20 sessions, excluding the last session. Zero baseline is unavailable. |

Insufficient evidence is `null` and displayed as “Unavailable.” RSI is initialized inside the 60-session window, so it can differ from a provider using a longer warm-up. Decimal arithmetic classifies thresholds before display rounding; rounded percentages near a boundary may look equal while the exact underlying result differs.

**Raw-price screening:** before selecting real rounds, every research-plus-outcome candidate window is checked for adjacent close-to-open or close-to-close jumps of 18% or more. Such windows are excluded, with no guessed adjustments. This is a conservative distortion screen, **not verified corporate-action data**: smaller splits, dividends, erroneous sessions and missing exchange sessions can escape it; large genuine market moves can be excluded. Real prices remain explicitly unadjusted. No exchange calendar or split endpoint is fetched. These limitations must remain visible in project descriptions.

Real rounds randomly select a valid triple of screened cutoffs, kept chronological and at least five sessions apart. This prevents an earlier reveal from exposing a later hidden outcome. With compact history, research windows overlap and the finite pool can repeat across games; a minimally sufficient 75-session dataset has only one valid triple. The chosen single real ticker becomes known after the first reveal even though subsequent research payloads still omit it. Randomization uses this existing dataset without fetching additional stocks or history.

Synthetic games sample three distinct pattern families from upward trend, downward trend, sideways, choppy, high volatility, upward reversal, downward reversal and breakout. Each path has randomized parameters, OHLC and volume. All 65 sessions of all three scenarios are generated before gameplay; the chart, indicators, analyst evidence and reveal use those same immutable datasets. Duplicate paths within a game are excluded. Outcomes follow the generated prices naturally: there is no requirement to include one of each answer. Research still uses ASSET A / B / C and the visible synthetic label.

For reproducible automated fixtures, call `synthetic(seed=113)`. Real-window selection can be reproduced with `Game.create((dataset,), notice, seed=113)`. Omitting the seed uses fresh randomness in normal gameplay. These seeds control datasets/window selection, not session or round identifiers.

## Outcomes and points

Compare the last visible close with the fifth subsequent session's close:

- **DOWN:** return below −1%.
- **FLAT:** return from −1% through +1%, inclusive.
- **UP:** return above +1%.

Correct calls earn **100 accuracy points**, plus `floor(seconds remaining / 3)` speed points (0–20), plus `10 × (current correct streak − 1)` combo points (0, 10, 20). Maximum three-round score is 390. Incorrect calls earn zero and reset the combo. Timeout without a choice shows **No call**, earns zero, and resets the combo. Speed is awarded only for correct calls. Every reveal shows the point breakdown before proceeding; the third reveal leads to the final summary and replay control.

## OpenAI analyst

Official sources checked on 2026-09-19: [Responses API](https://developers.openai.com/api/docs/guides/text), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

The backend posts to `https://api.openai.com/v1/responses` using bearer authentication. It sends the player's **actual question**, at most three recent questions, calculated historical evidence and a constrained response schema. No real ticker, dates, hidden outcome, future prices, browsing tools or external-history tools are supplied. A player can type arbitrary text, but this does not grant the analyst additional data access.

The model selects relevant evidence IDs, explanation IDs and limitation IDs. The backend validates all selected references and renders numerical facts from its calculated values. Explanations are a small audited set, with conflicting-return commentary derived from the actual evidence. **This is constrained evidence selection, not unrestricted model-authored prose.** It intentionally trades conversational freedom for checkable facts and prevents prediction recommendations by construction. The UI attributes successful responses as OpenAI-selected evidence. Unavailable news, earnings, future information and decision requests receive explicit limitations. Off-topic details cannot be fabricated through the schema.

Only one analyst request can be outstanding for the local app; no fixed per-round question count. Requests are separated by at least two seconds, with a 60-second cooldown after a provider 429. Questions are capped at 600 characters; output at 300 tokens; no automatic retries. No OpenAI calls happen during refreshes, countdowns or polling. Six exchanges are retained in memory per round; no conversation transcripts are written to disk. Only token counts and timestamps are appended to ignored `.local/usage.jsonl`, including usage from completed HTTP responses that subsequently fail content validation. If a usage-log write fails, counts remain in memory and the UI reports the issue.

Missing credentials, invalid structured output, refusals/incomplete output, HTTP failures, network errors and timeouts produce **Analyst temporarily unavailable**. There is no offline AI impersonation or successful canned fallback. The analyst's response quality and actual model/account compatibility remain unverified until a real request succeeds.

## Files and Git hygiene

| File | Responsibility |
| --- | --- |
| `run.py` | Local configuration and CLI; loopback-only launch. |
| `arcade/data.py` | Stock request, validation, metadata, cache, raw-price screening and fictional generator. |
| `arcade/game.py` | Research slices, indicators, deadlines, outcomes and points. |
| `arcade/analyst.py` | Bounded OpenAI request, evidence validation and token accounting. |
| `arcade/server.py` | Session cookies, local API routes and safe public responses. |
| `static/` | HTML, CSS and JavaScript; canvas price/volume chart. |
| `tests/` | Standard-library unittest suite with HTTP mocks and temporary caches. |
| `.env.example` | Blank public configuration template. |

The original useful `.gitignore` rules were retained. The only additional exclusions for this implementation are `/.local/` and a precise exception allowing the blank `/.env.example`. Existing environment, Python cache/venv, Streamlit secrets, VS Code and OS rules remain. No blanket JSON/CSV/text/image exclusions were added. The effective ignore audit covers `.env`, environment variants, `.venv`, downloaded data, usage logs, Python caches, editor files and Streamlit secrets. Both tracked and staged filenames were checked: **no tracked ignored/private-file problems found**, and no files were staged by this work. Ignoring a file does not untrack an already committed copy.

Only `static/` is mounted for browser assets. `.env` and `.local` cannot be served as files. Session cookies are HttpOnly and SameSite Strict; mutation routes require a local custom header and reject cross-origin requests. This is a single-process local app, not a hardened public service. Do not expose it on the public internet.

## Development / prompt log

The pre-existing [prompt_log.md](prompt_log.md) is preserved unchanged as a historical artifact. Its existing “AI models” and “Keyprompt” text belong to that file; they are not a reconstructed ChatGPT history. No instructor-specific format or assignment sheet was found in the repository.

The following are **summaries of actual user prompts to Codex**, not verbatim transcripts or in-game analyst conversations:

| Date | Prompt summary | Work actually performed |
| --- | --- | --- |
| 2026-09-19 | Inspect and update only `.gitignore` for local environment secrets, Python venv/cache files, Streamlit, VS Code and OS files; preserve existing rules and keys. | Added missing patterns and verified 20 sample ignore paths. No keys read or added. These rules were present at the start of the larger build. |
| 2026-09-19 | Inspect the existing Arcade project first; then build the complete local three-round Python game, starting with Alpha Vantage, explicit stock modes, strict historical boundaries, Python evidence, OpenAI analyst, safe credentials, tests, README and submission guidance. Preserve existing work, use $0 additional spending, proceed without per-file approvals, and report unverified live integrations. | Inspected all tracked project files and Git status; preserved the existing log; checked official API documentation; built the data layer, game engine, analyst, FastAPI routes and browser terminal; created blank local/template configuration; installed the four dependencies in `.venv`; ran mocked tests and Chrome checks; documented constraints and handoff. |
| 2026-09-19 | Inspect the working project before editing; improve start/end screens, summary statistics, LINE/CANDLE chart views, terminal density, Analyst Desk separation, anonymity and result reveals. Preserve provider integrations, scoring, timeout, future-data boundaries, keys, tests and the existing structure; do not commit or push. | Confirmed a clean Git state and 25 passing baseline tests. Updated the three existing frontend files, added minimal server-owned summary/question accounting, extended existing tests, and updated this README. All 28 tests passed. Chrome checks verified start gating, both chart views, post-call candle reveals, timeout, final summary, replay reset and the separately styled analyst response/evidence using labeled HTTP mocks. No dependencies or live API requests were added. |

Completed checks: 25 passing tests covering invalid input/tickers, insufficient/malformed OHLCV, duplicate JSON/dates, rate/HTTP/JSON/network/timeout failures, cache reuse/write failure, explicit fallback, synthetic determinism, split-like jumps, evidence isolation, threshold inclusivity, scoring, duplicate/stale/late predictions, timeout, analyst validation/unavailability, concurrency, three-round replay API flow and local HTTP protection. Compilation and Git whitespace checks passed. Desktop Chrome rendered the price/volume chart and showed all three rounds, prediction results, a real 60-second timeout, final score, replay reset, and a correct call awarding accuracy/speed points. **Pending checks:** actual provider requests after local key setup, real analyst answer relevance, and broader mobile/browser testing.

Additional prompt summary, 2026-09-19 (not verbatim): refine the analyst area into an unmistakable chat interface with a stronger header, distinct roles and message cards, separated evidence, an obvious interactive composer and a conversational empty state; keep backend/OpenAI logic and game flow unchanged, with no commit or push. Completed: refined the existing HTML/CSS/JS and updated this README. The 28 existing tests passed. Chrome checks used explicitly labeled mocked responses to inspect the empty state, question/response bubbles, evidence cards, Enter-to-send and disabled chat after timeout. No dependencies, provider requests or backend changes were introduced in this pass.

Additional prompt summary, 2026-09-19 (not verbatim): replace the three fixed scenarios with fresh randomized rounds on every new game and Play Again; provide varied synthetic patterns, no duplicate scenario within a game, natural answers, fixed hidden outcomes and seedable tests; randomize existing real windows without extra stock requests, preserve the UI and working logic, run tests, and do not commit or push. Completed: expanded the synthetic generator to eight pattern families, regenerated synthetic paths per new game, randomized chronological real windows with separate outcome intervals, and extended existing tests. All 35 tests passed, including seeded reproducibility, natural answer variation, fixed outcomes, research/evidence consistency, replay in demo and auto fallback, active-session isolation, and real-data reuse. Python compilation and Git whitespace checks passed. The UI, analyst implementation and dependencies were unchanged; no live provider requests were made in this pass.

## Recording and submission

Use synthetic data for public portfolio material unless permission to publish downloaded real provider data has been verified. Keep `.local/` out of GitHub and out of recordings. A suggested recording sequence:

1. Start `--mode demo`; show the fictional-data banner and explain the stock/analyst separation.
2. Show the stock adapter's documented request parameters and mocked test results, explicitly calling the live stock connection unverified until it succeeds. If privately verifying stock live mode later, do not expose a keyed URL or publish the returned data without permission.
3. With OpenAI configured locally, ask a real question and show the user input, analyst response, token usage, and how the same research data drives the chart and Python evidence. If credentials are still absent, label that segment as pending rather than claiming real communication.
4. Commit a call, show the five-session reveal and points, finish the three rounds, and demonstrate replay.
5. Demonstrate a graceful failure, such as the no-key analyst state or auto-mode synthetic fallback. Do not show the contents of a configured `.env` on screen.

Submission checklist (manual actions; not performed automatically):

- [ ] Publish code, README and development/prompt log in the **required public GitHub repository**, after checking the staged filenames for secrets and provider datasets.
- [ ] Record the demo video and upload it to the location required by the assignment.
- [ ] Complete the course Google submission form before the deadline.
- [ ] Confirm the original assignment's exact repository requirements, video length/hosting requirements, Google form URL and deadline. None were available here; no values have been invented.
