# Prompt Log

API AI models: gpt-5.6-lna
AI models: ChatGPT 6 Astra

Keyprompt:

"I'm working on a AI API project, and I have ideas in my mind, and I would like you to help me to implement those. And here are some of the designs I've been thinking.


I want to make a short Wall Street-style stock prediction game. The main focus should still be the API communication, and the game is more like the experience built around it.

The game should have around 3–5 short rounds. For each round, give the player a historical stock chart and a short research period. The player should be able to talk to an AI analyst and ask questions about the stock, like recent performance, volatility, volume, RSI, moving averages, or anything else related to the available market data.

The AI analyst should answer based on real data retrieved from the stock API. Do not let the AI make up numbers or use future information that the player is not supposed to know.

The player can ask as many questions as they want while the timer is running. Before time runs out, they choose:

DOWN / FLAT / UP

After the player makes a choice, reveal what actually happened during the next few trading days and give them points based on accuracy, speed, and combo.

The basic loop is:

Look at chart → Ask AI analyst questions → Make a call → Reveal result → Get points → Next round.

Keep the game short, simple, and arcade-like. It should feel like a simplified Wall Street trading terminal, with a dark interface, financial charts, clean typography, countdown timer, and fast transitions. Do not turn it into a large financial dashboard or realistic trading simulator.

The API implementation is the main priority. Start by getting one clean stock API request working first, then build the game around it.

The project should do more than just fetch and print data. It should use the returned data for the chart, financial calculations, AI analyst responses, and the final game result.

Please keep the architecture simple and understandable. Prefer Python if it makes handling API keys and AI communication easier.

Important requirements:

* Keep all API keys and secrets outside the code and GitHub repo.
* Use environment variables or a local config file that is included in .gitignore.
* Do not expose private API keys in frontend JavaScript.
* Handle bad or empty input without crashing.
* Handle missing stock data or invalid tickers.
* Handle API errors, rate limits, and network failures with useful messages.
* Test the project by intentionally breaking these cases.


Keep the scope reasonable. 

Before implementing everything, ask me any question you may have."

Codex Implementation
"You are working in my existing GitHub project folder for “Arcade financial analyst.”

This is the first project instruction I am giving you. Do not assume you have received previous prompts, files, or design documents from my ChatGPT conversation.

WORKFLOW

Create, edit, organize, run, and test all necessary project files directly. Do not merely print scripts or ask me to create the files myself.

I will discuss design decisions separately in ChatGPT and bring you follow-up instructions when necessary.

First inspect the repository without changing files. Review the existing source files, README, dependencies, .gitignore, and Git status. Preserve existing work.

Before implementation, ask any genuinely unresolved questions together in one short batch. Do not ask me to reconfirm decisions already specified in this prompt. If nothing needs clarification, proceed.

Briefly explain your implementation plan, then build the project in manageable stages. Start with the stock-data API integration, but continue toward the complete working local game.

After implementation begins, ask questions only when an important decision or missing authorization genuinely blocks progress. Do not require approval after every file.


1. PROJECT GOAL AND ENVIRONMENT

Create a short Wall Street-style stock prediction game.

The API communication is the main focus. The game is the experience built around it, not a large financial dashboard or realistic trading simulator.

The application will run locally on my Windows computer and be played in a browser. Its source code will go on GitHub. Later, I will use screenshots and a recorded playthrough for my portfolio.

I have redeemed $10 of OpenAI API credit to my personal account. I do not yet have a stock-data API key.

Keep additional spending at $0. Do not purchase services or choose paid stock-data features without asking.

Missing credentials must not stop the rest of implementation. Continue with synthetic stock data and mocked API responses for tests. Clearly mark live integrations as unverified until credentials are configured and requests succeed.


2. GAME DESIGN

Build exactly 3 rounds.

Each round:
1. Shows 60 historical trading sessions.
2. Gives the player 60 seconds to research.
3. Lets the player ask an AI analyst questions about the available data.
4. Requires the player to choose DOWN, FLAT, or UP.
5. Reveals the following 5 trading sessions after commitment or timeout.
6. Shows the result and points before continuing.

Measure the outcome using the percentage change from the last visible closing price to the fifth subsequent trading session’s closing price:
- DOWN: below -1%.
- FLAT: -1% through +1%, inclusive.
- UP: above +1%.

Start the countdown only when the round’s data and chart are ready. It continues while the analyst responds.

Allow questions throughout research without a fixed question-count limit, but allow only one outstanding analyst request at a time and respect provider limits.

A submitted prediction is final. On timeout without a choice, show “No call,” award zero points, and reset the combo.

Accuracy should provide most points. Add smaller speed and consecutive-correct-answer combo bonuses. Choose simple, transparent scoring values and document them. Award speed bonuses only for correct predictions.

Show a final score after round 3 and allow the player to start again.

During research, use anonymous stock labels, relative trading days, and indexed prices. Reveal the real stock and dates afterward. Keep synthetic rounds clearly identified as fictional throughout.


3. STOCK DATA AND FALLBACKS

Start with Alpha Vantage as the intended provider. Check its current official documentation and use an appropriate free historical daily-data endpoint. Do not silently use premium features.

First establish the stock-request function, response validation, and reusable data format. Then build the other components around it.

Use a consistent format containing:
- date
- open
- high
- low
- close
- volume

Store source, symbol, download time, and price-basis information as metadata.

Make the stock ticker configurable through a simple command-line option or local configuration rather than hard-coding one symbol. Normal gameplay should still hide the chosen stock’s identity. Document the stock request parameters in the README.

Support three explicit stock-data modes:
- live: attempt a real API request and report failure without silently substituting synthetic data.
- auto: use valid cached real data; otherwise try the API; if unavailable, clearly announce synthetic fallback.
- demo: generate deterministic fictional stock data without stock credentials or a stock API request.

Save successful real downloads locally and reuse them for development and gameplay. Use the returned dataset for the chart, financial calculations, analyst evidence, and final result. Do not request stock data again for every analyst question.

Reject blank or malformed tickers. Handle provider-rejected tickers explicitly rather than disguising them as successful real-data loads.

Validate chronological ordering, duplicate dates, numerical values, OHLC consistency, and sufficient history for the 60-session research window and 5-session outcome. Do not invent missing real prices.

Handle missing credentials, empty or incomplete data, invalid JSON, HTTP failures, rate-limit notices, timeouts, network failures, and cache errors with useful messages.

Synthetic data must:
- Use fictional identifiers and a visible SYNTHETIC DEMO label.
- Provide varied scenarios for the three rounds.
- Be generated before the player makes a choice.
- Supply the same underlying evidence for charts, calculations, and results.
- Never change the outcome after the player’s choice.
- Never be presented as proof that the real stock API connection works.

Stock-data mode and analyst availability are independent. Synthetic stock data may still be analyzed through the real OpenAI API when its key is configured. Without an OpenAI key, keep the game playable and show the analyst as unavailable; do not fabricate an AI response.

Before selecting real scenarios, review raw-price windows for stock-split distortions or use verified split-adjusted data. Document remaining limitations instead of guessing adjustments.


4. HISTORICAL BOUNDARY AND CALCULATIONS

Separate each round’s permitted research data from its hidden outcome on the Python backend.

Calculate returns, moving averages, RSI, volatility, and volume comparisons in Python using only data available at or before the cutoff. Document the indicator definitions and mark unavailable calculations honestly.

Do not send hidden prices, the correct answer, real ticker, or actual calendar dates to the analyst during research.

Do not send future prices or results to the browser before commitment or timeout. Do not include them in HTML, JavaScript, or an API response and merely hide them visually.

Keep deadlines, prediction acceptance, reveal authorization, and scoring authoritative on the backend. Reject duplicate or late submissions appropriately.

Fix each round’s outcome before the player makes a choice.


5. AI ANALYST

Use the OpenAI API for the analyst.

The analyst explains facts, evidence, conflicting signals, and limitations. It must not choose or recommend DOWN, FLAT, or UP, even when the player asks it to make the decision.

Use the player’s actual question in analyst requests rather than a fixed question. Send only that question, necessary conversation context, and permitted numerical evidence.

The analyst must not browse the web, fetch unrestricted market history, or access the hidden outcome.

Questions about unavailable news, earnings, or other missing information should receive an honest explanation of what is unavailable.

Use Python-calculated values as the source of numerical facts. Render numerical evidence from verified values and validate evidence references or numerical claims rather than relying solely on a “do not hallucinate” instruction.

Use a configurable inexpensive model. Verify current official OpenAI documentation when implementing the connection.

Keep replies short, bound conversation history and retries, and record token usage without logging secrets.

Do not make model calls during countdown updates, screen refreshes, or automatic polling.

If OpenAI is unavailable, show “Analyst temporarily unavailable” while keeping the chart and prediction controls usable. Do not present canned text as a successful AI response.


6. INTERFACE AND ARCHITECTURE

Use a simple Python backend, preferably FastAPI, with straightforward HTML/CSS/JavaScript unless the existing repository gives a good reason to do otherwise.

Keep the interface focused:
- Historical chart and volume information.
- Current round, score, and countdown.
- Analyst conversation and question input.
- DOWN / FLAT / UP buttons.
- Result reveal and final score.

Use a dark trading-terminal aesthetic, clean typography, readable charts, restrained color, and quick transitions.

Prefer a small number of clearly separated components over either one huge script or an unnecessarily elaborate folder structure.

Run the server locally on 127.0.0.1.

Do not add public deployment, accounts, a database, multiplayer, trading execution, Docker, or a large frontend framework.


7. REPOSITORY AND CREDENTIALS

You may inspect and modify project files as needed. Preserve existing work and handle any existing credentials confidentially.

I have already made additions to .gitignore. Inspect it first, retain useful existing rules, and add only missing exclusions.

Check both effective ignore behavior and tracked/staged filenames. An ignored file might already be tracked. Report any such problem by path only; do not expose its contents, automatically remove tracked files, or rewrite Git history.

Keep private configuration, the virtual environment, downloaded caches, generated logs, and machine-specific output outside GitHub.

Do not use broad ignore rules that hide all JSON, CSV, text, or image files.

Create or maintain a blank .env.example with the required variable names, including:
- ALPHAVANTAGE_API_KEY
- OPENAI_API_KEY

Create a private placeholder .env only when absent and after verifying that it is ignored. Never overwrite existing keys.

I will obtain API keys and enter them locally when needed. Tell me exactly where to enter them, but never ask me to paste credentials into chat.

Use each provider’s documented authentication method over HTTPS from the backend only.

Never expose credentials in frontend JavaScript, committed files, documentation, screenshots, or logs. Never display or log complete request URLs containing API keys, including through error messages.

Maintain requirements.txt with only packages actually needed.

Do not create another Git repository or commit/push automatically.


8. DOCUMENTATION AND ASSIGNMENT SUBMISSION

Keep project requirements, setup instructions, current implementation status, limitations, and a compact development/prompt log in README.md for now.

Preserve an existing assignment log if there is one. Follow any instructor-specified documentation or log format available in the repository rather than replacing it with an assumed format.

The development prompt log records prompts used to build the project. It is not a log of the player’s in-game analyst conversations.

Record the prompts I actually provide to Codex and the work actually performed. Distinguish verbatim prompts from summaries and completed checks from proposed checks.

Earlier ChatGPT design conversations are not available unless I supply them. Do not invent or reconstruct that history.

Avoid separate planning documents, duplicated READMEs, backup scripts, empty directories, unused dependencies, and reports that I have not requested.

Add a short submission checklist to the README covering:
- Code, README, and prompt log published in the required public GitHub repository.
- Demo video recorded and uploaded.
- Course Google submission form completed before the deadline.

Include a brief suggested recording sequence showing API communication, user input, meaningful use of returned data, gameplay, and a gracefully handled failure.

Do not invent a video-length requirement, submission URL, or deadline. Identify any submission details that still need confirmation from the original assignment instructions.

Preparing these materials does not authorize you to publish, upload, or submit anything automatically. Report the remaining submission actions for me to complete.

Keep downloaded provider datasets out of the public repository. Use clearly labeled synthetic scenarios for public demo material unless permission to publish the real data has been verified.


9. TESTING AND VERIFICATION

Keep a small, useful test suite. Test relevant components during implementation, not only at the end.

Cover:
- Missing credentials and blank or invalid inputs.
- Invalid tickers and insufficient or malformed stock data.
- Provider errors, rate limits, timeouts, and network failures.
- Cache and synthetic fallback behavior.
- Analyst failures and requests for unavailable or future information.
- Historical-data boundaries.
- Outcome thresholds, including exactly -1% and +1%.
- Scoring, timeout, and duplicate submissions.

Use mocks for repeated failure tests rather than exhausting live quotas. Use temporary test data and cache locations.

Do not make network calls during module imports or ordinary mocked tests.

Make only minimal deliberate live connection checks when credentials are configured. Report which external connections were actually verified and which were only mocked.

Do not claim the complete project or an API integration works unless the relevant checks support that claim.


10. BUILD ORDER

1. Inspect the repository and audit configuration and .gitignore.
2. Implement and test stock-data loading, caching, and synthetic mode.
3. Prepare historical rounds and numerical evidence.
4. Implement the OpenAI analyst.
5. Build one complete playable round.
6. Complete the three-round flow, scoring, and interface.
7. Run checks and finish the README.

Work through these stages without requiring my approval after every file. Do not stop at the first data-loading script.


11. FINAL HANDOFF

At the end, summarize:
- What was built and which files matter.
- The .gitignore audit and any unresolved tracked-file issues.
- Tests and live API checks actually performed.
- Remaining limitations, unverified connections, or blockers.
- Exact PowerShell commands to set up and run the game.
- Where I must enter each API key locally.
- Remaining recording, publishing, and assignment-submission actions for me to complete."

Improvement:

"I have a working version of the game now. Before changing anything, inspect the current project and keep the existing backend/API logic working.

I want to improve the game mainly from the UI and game-flow side.

Please make these changes:

1. Add a real start screen before Round 1.
   - Show the game title, 3 rounds, 60 seconds per round, and a Start button.
   - Do not start the timer until I press Start.

2. Add a proper end screen after Round 3.
   - Show final score, correct predictions, best combo, and analyst question count.
   - Add a Play Again button that fully resets the game without refreshing the page.

3. Improve the chart.
   - Keep the current line chart.
   - Add a candlestick / K-line view using the existing OHLC data.
   - Let me switch between CANDLE and LINE.
   - Keep volume underneath.
   - Do not expose the hidden 5 future sessions before the prediction.

4. Make the interface feel more like a Wall Street trading terminal.
   - Keep the current dark style because I like the direction.
   - Make the layout denser, cleaner, and more financial/trading-terminal-like.
   - Avoid flashy casino/neon styling or adding unnecessary dashboard features.

5. Make the AI analyst area feel more separate from the market panel.
   - Make it look more like an “Analyst Desk”.
   - Clearly separate my questions, AI responses, and verified numerical evidence.
   - Keep the current OpenAI logic and evidence validation.
   - The analyst still should not choose UP / DOWN / FLAT for me.

6. Keep the anonymous stock design.
   - During research, keep names like ASSET A.
   - In demo mode, keep it clearly labeled as synthetic and do not invent a real company.
   - In real-data mode, reveal the real ticker/name only after I make the prediction.

7. Improve the result reveal.
   - After I choose, show my call, actual 5-session return, correct direction, and score breakdown.
   - If it is easy with the current chart setup, reveal the hidden 5 sessions on the chart after the call.
   - Do not make the animation slow.

Please preserve:
- OpenAI integration
- live / auto / demo stock modes
- scoring logic
- timeout behavior
- hidden future-data boundary
- API key handling
- existing tests

Do not redesign the backend unless necessary for these features.
Do not add accounts, database, public deployment, trading execution, or unnecessary frameworks.

Keep the current file structure clean and reuse existing files where possible.

After you finish:
- run the tests
- tell me what files changed
- tell me if you added any dependency
- tell me what could not be implemented cleanly
- give me the command to run the updated game

Do not commit or push. I want to test it first."

Final fixes for adding scenerios:

"Everything is looking good now. I only want one more gameplay change.

Right now there are only 3 fixed scenarios, so replaying the game gives the same rounds.

Please change this so every new game / Play Again gives me 3 different randomized scenarios.

For demo/synthetic mode:
- generate a larger variety of market patterns instead of 3 fixed datasets
- randomly select/generate 3 scenarios for each game
- avoid using the exact same scenario twice within one 3-round game
- give the scenarios different behaviors, such as upward trend, downward trend, sideways/choppy, high volatility, reversals, etc.
- do not intentionally make the three answers always one DOWN, one FLAT, and one UP; let the actual generated data determine the result naturally

Important:
- generate the full scenario, including the hidden 5 sessions, before the round starts
- once generated, never change the hidden outcome based on the player's decision
- the AI analyst, indicators, chart, and final result must all use the same generated dataset
- Play Again should generate/select a fresh set of 3 rounds
- keep the anonymous Asset A / B / C labels
- keep synthetic data clearly labeled as synthetic

For testing, make the random generator seedable so automated tests can still reproduce the same scenario when needed, but normal gameplay should be random.

If real stock mode already supports multiple possible historical windows/stocks, randomize those appropriately too without exposing the stock identity before reveal. Do not add unnecessary live API requests just to randomize rounds; reuse cached data where possible.

Keep everything else as it is. Do not redesign the UI or refactor unrelated working code.

Run the tests afterward and tell me what changed. Do not commit or push."