# SIGameBot

SIGameBot is a multiplayer Jeopardy-like (SI Game) bot for Telegram group chats.
The gameplay interface is in Russian.

## Table of Contents

- [Features](#features)
- [Quick Start (Docker)](#quick-start-docker)
- [How to Play](#how-to-play)
- [Managing Topics and Questions](#managing-topics-and-questions)
- [Shop and Balance (Private Chat)](#shop-and-balance-private-chat)
- [Admin HTTP API](#admin-http-api)
- [Configuration Reference](#configuration-reference)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- Multiplayer game sessions in Telegram group chats
- Host-controlled lobby, game flow, scoring, and buzzer rounds
- Topic/question management in private chat with the bot
- In-game shop and balance system
- Optional answer-similarity support via OpenRouter LLM API
- Optional FastAPI admin API for managing users/games/topics/questions

## Quick Start (Docker)

### 1) Prerequisites

- Docker Engine + Docker Compose plugin
- Telegram account
- A bot token from [@BotFather](https://t.me/BotFather)

Verify Docker:

```bash
docker --version
docker compose version
```

### 2) Clone the repository

```bash
git clone https://github.com/arniknz/SIGameBot.git
cd SIGameBot
```

### 3) Configure environment variables

```bash
cp .env.example .env
```

At minimum, set:

```dotenv
BOT_TOKEN=123456789:ABCdefGHI-jklMNOpqrSTUvwxYZ
```

Optional (for LLM-based answer similarity):

```dotenv
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=qwen/qwen3-next-80b-a3b-instruct:free
OPENROUTER_MODEL_FALLBACKS=
```

### 4) Start services

```bash
docker compose up --build -d
```

This starts:
- `db` (PostgreSQL)
- `rabbitmq`
- `bot`
- `admin_api`

The bot container applies Alembic migrations on startup.

### 5) Check health

```bash
docker compose ps
docker compose logs bot
```

Look for `Bot is running` in bot logs.

### 6) Stop services

```bash
docker compose down
```

Remove all persisted game data:

```bash
docker compose down -v
```

## How to Play

### Setting Up a Game (Group Chat)

1. Add the bot to a Telegram group chat.
2. Any member sends `/start` to create a new game and become host.
3. Players join with **Войти**, spectators use **Смотреть**.
4. Host starts the game with **Старт** or `/start_game` (minimum 2 players).

The lobby message includes inline buttons:

- **Войти** · **Смотреть** — join as player or spectate  
- **Выйти** · **Счёт** — leave game, show score  
- **Правила** · **Справка** — open Rules and Help in a **private chat** with the bot  
- **Старт** · **Стоп** — start game, stop game (host)  
- **Магазин** — open Shop in private chat  
- **Управление в личке** — open bot DM for managing topics and questions  

### During the Game

1. A random player picks the first question.
2. The bot shows topics and prices; the current player selects a cell.
3. Everyone has `BUZZER_TIMEOUT` seconds to press **Звонок**.
4. First buzzed player has `ANSWER_TIMEOUT` seconds to answer.
5. Correct answer: points added, player chooses next.
6. Wrong answer: points deducted, correct answer shown, same player chooses next.
7. No buzz: correct answer shown, same player chooses next.
8. Game ends when all questions are used, then final scoreboard is shown.

### Commands in Group Chat

| Command | Description |
|--------|-------------|
| `/start` | Create a new game (you become host) |
| `/start_game` | Start the game (host only) |
| `/score` | Show current scoreboard |

Join, leave, spectate, start, stop, score, rules, help, and shop are also available as **inline buttons** under the lobby/game message. **Правила** and **Справка** open the bot in private chat to avoid spamming the group.

## Managing Topics and Questions

Topics and questions are managed in a **private chat** with the bot (click **Управление в личке** in the lobby or message the bot directly).

| Command | Description |
|--------|-------------|
| `/add_topic` | Create a new topic (bot asks for a name) |
| `/add_question` | Add a question (step by step: topic, question text, answer, cost) |
| `/delete_topic` | Delete a topic and all its questions |
| `/delete_question` | Delete a single question |
| `/restore_topic` | Restore a previously deleted topic |
| `/restore_question` | Restore a previously deleted question |
| `/my_games` | List games where you are host (with links to open the group) |
| `/help` | List all commands |
| `/rules` | Show game rules |
| `/cancel` | Cancel current action |

In group chats, `/help` and `/rules` redirect users to private chat.

## Shop and Balance (Private Chat)

In private chat with the bot:

| Command | Description |
|--------|-------------|
| `/shop` | Open the in-game shop (categories and items) |
| `/balance` | Show your coin balance and daily reward info |

Use the **Магазин** button in the lobby to open the shop in private chat. Items can be used during the game (e.g. hints, double points).

## Admin HTTP API

`docker compose` also starts `admin_api` (FastAPI) on:

- `http://localhost:${ADMIN_API_PORT}` (default: `8000`)
- OpenAPI docs: `http://localhost:${ADMIN_API_PORT}/docs`

Default credentials from `.env.example`:

- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=secure123`

Change these values in `.env` before exposing the API anywhere.

## Configuration Reference

All settings are read from `.env`.
Only `BOT_TOKEN` is strictly required for basic bot startup.

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | *(required)* | Your Telegram bot token from BotFather |
| `DB_HOST` | `localhost` | PostgreSQL host (set by Docker for the bot) |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `sigamebot` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ host |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |
| `RABBITMQ_USER` | `guest` | RabbitMQ user |
| `RABBITMQ_PASSWORD` | `guest` | RabbitMQ password |
| `WORKERS_COUNT` | `3` | Number of concurrent update workers |
| `LOBBY_TIMEOUT` | `3600` | Lobby timeout in seconds |
| `QUESTION_SELECTION_TIMEOUT` | `30` | Seconds for the current player to choose a question |
| `BUZZER_TIMEOUT` | `10` | Seconds to wait for a buzzer press |
| `ANSWER_TIMEOUT` | `15` | Seconds to wait for an answer after buzzing |
| `LOG_LEVEL` | `INFO` | Log verbosity: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `logs/bot.log` | Log file path (auto-rotated at 10 MB) |
| `ADMIN_USERNAME` | `admin` | Basic auth username for admin API |
| `ADMIN_PASSWORD` | `secure123` | Basic auth password for admin API |
| `ADMIN_API_PORT` | `8000` | Port for the optional admin API (when running with docker compose) |
| `OPENROUTER_API_KEY` | `your_api_key_here` | API key for OpenRouter integration |
| `OPENROUTER_MODEL` | `qwen/qwen3-next-80b-a3b-instruct:free` | Primary LLM for answer similarity |
| `OPENROUTER_MODEL_FALLBACKS` | *(empty)* | Comma-separated fallback LLM models |
| `MAX_CSV_ROWS` | `1000` | Max CSV rows for question import operations |

When using Docker, `DB_HOST`, `DB_PORT`, and RabbitMQ settings are applied by `docker-compose.yml`; you usually only set `BOT_TOKEN` and optionally the timeouts and log level.

## Development

### Local Python setup

Use Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
```

### Run bot locally

```bash
alembic upgrade head
python -m bot.main
```

### Lint and format checks

```bash
ruff check .
```

Auto-fix:

```bash
ruff check --fix .
```

### Run tests

```bash
pytest
```

## Troubleshooting

- If `bot` cannot connect to Telegram, verify `BOT_TOKEN`.
- If `db` is unhealthy, inspect `docker compose logs db`.
- If migrations fail, inspect `docker compose logs bot`.
- If admin API auth fails, verify `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
- If answer similarity is unavailable, configure `OPENROUTER_API_KEY`.

## License

MIT
