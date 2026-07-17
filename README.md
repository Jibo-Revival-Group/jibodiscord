# Jibo Discord Bot

A Python Discord bot that lets you talk to **Jibo** using `/ask` or `!ask`, and ask an AI grounded in Discord community history with `/ai` or `!ai`. Jibo responses are driven by [OpenJibo](https://github.com/Jibo-Revival-Group/JiboExperiments) — the open-source cloud replacement for physical Jibo robots.

## How it works

1. Your message is normalized (like OpenJibo's transcript handling).
2. A semantic intent is resolved using phrase rules ported from `JiboInteractionService.IntentRouting`.
3. A reply is chosen from:
   - Embedded seed catalog (from OpenJibo's `InMemoryJiboExperienceContentRepository`)
   - Thousands of legacy `.mim` prompt files from your local OpenJibo checkout
4. Skills like jokes, math, dice rolls, and personality questions behave like the real cloud brain.

## Setup

### 1. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create an application → **Bot** → reset/copy the token.
3. Enable **Message Content Intent** under Privileged Gateway Intents (needed for `!ask`).
4. Invite the bot with `applications.commands` and `bot` scopes.

### 2. Install dependencies

```bash
cd jibo-discord-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

- `DISCORD_TOKEN` — your bot token
- `DISCORD_GUILD_ID` — Discord server snowflake ID; the bot only stays in this guild and leaves any other server it joins
- `OPENJIBO_PATH` — path to your OpenJibo checkout (default: `~/JiboExperiments/OpenJibo`). Used for `.mim` response data and API settings from `appsettings.json`.
- `USE_FUN_FACT_API` — set to `false` to use only local fun-fact fallbacks
- `OPENAI_API_KEY` — required for `/ai` and `!ai` (falls back to a `chatgpt!KEY` value from knowledge search settings if unset)
- `OPENAI_AI_MODEL` — model for `/ai` (default: `gpt-4.1-mini`)
- `OPENAI_VECTOR_STORE_ID` — Discord history vector store (default: `vs_6a5a46ef89408191bb8ce3cf2a6f132d`)

When `OPENJIBO_PATH` points at a real OpenJibo checkout, the bot automatically loads API keys from `src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Api/appsettings.json`:

| Service | OpenJibo section | Env override |
|---------|------------------|--------------|
| Weather | `OpenJibo:Weather:OpenWeather` | `OPENWEATHER_API_KEY`, etc. |
| Fun facts | `OpenJibo:FunFacts:UselessFacts` | `USELESS_FACTS_BASE_URL` |
| Dictionary | `OpenJibo:Dictionary:FreeDictionaryApi` | `FREE_DICTIONARY_BASE_URL` |
| News | `OpenJibo:News:NewsApi` | `NEWSAPI_KEY`, etc. |
| Knowledge search | `OpenJibo:Search` | `OPENJIBO_SEARCH_BACKEND`, `OPENJIBO_SEARCH_FALLBACK` |
| Discord AI (`/ai`) | — | `OPENAI_API_KEY`, `OPENAI_AI_MODEL`, `OPENAI_VECTOR_STORE_ID` |

Knowledge search uses OpenJibo's backend spec format, e.g. `wolfram!APPID`, `chatgpt!APIKEY!MODEL`, or `ollama!http://127.0.0.1:11434!llama3.1:8b`. The default OpenJibo config sets `Primary` to `none`, so search is off unless you configure it.

`/ai` and `!ai` use OpenAI's Responses API with `file_search` against a vector store of every message sent to the Jibo Discord, so answers lean on community troubleshooting and common Q&A.

### 4. Run

```bash
python bot.py
```

## Usage

| Command | Example |
|---------|---------|
| Slash | `/ask tell me a joke` |
| Prefix | `!ask what is your favorite color` |
| AI (Discord history) | `/ai how do I fix Wi-Fi on Jibo?` |
| AI prefix | `!ai how do I fix Wi-Fi on Jibo?` |

### Example questions

- `tell me a joke`
- `tell me a fun fact`
- `define robot`
- `what does empathy mean`
- `tell me the news`
- `what is your favorite color`
- `do you have a personality`
- `how old are you`
- `dance`
- `what is 9 plus 10`
- `roll a 20 sided die`
- `what time is it`
- `whats the weather today`
- `what's the weather in seattle`
- `what will the weather be tomorrow in boston`

## OpenJibo data

The bot reads legacy response scripts from:

```
$OPENJIBO_PATH/src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Infrastructure/Content/LegacyMims/
├── BuildA/
├── BuildB/
└── ReportSkill/
```

If OpenJibo is not found, the bot still runs using the embedded seed catalog.

## Project layout

```
bot.py              Discord entry point (/ask, !ask, /ai, !ai)
jibo/
  engine.py         Main Jibo brain — intent → reply
  intent_router.py  Phrase-based semantic intent routing
  catalog.py        Catalog loader + .mim merge
  seed_catalog.py   Inline seed responses from OpenJibo
  normalize.py      Transcript normalization
  config.py         Settings (auto-loaded from OpenJibo appsettings.json)
  providers/        External API clients (weather, news, dictionary, search, fun facts, Discord RAG)
  parsers/          Math, dice, and define command parsers
  weather/          Weather parsing, provider, and spoken reply formatting
  news/             News headline formatting
```

## Notes

- This emulates OpenJibo's **rule-based chitchat brain**, not the full WebSocket robot protocol.
- Clock intents follow OpenJibo's phrasing ("Showing the time.") with the actual time appended for Discord text chat.
- Personality replies are randomly selected from catalog lines, preferring snippet matches like the real `ScriptedResponseDecisionBuilder`.
