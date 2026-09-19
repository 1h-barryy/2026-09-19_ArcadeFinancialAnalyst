# Prompt Log

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