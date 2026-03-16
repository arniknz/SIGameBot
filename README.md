# SIGameBot

Multiplayer Jeopardy-like (SI Game) bot for Telegram group chats. Interface in **Russian**.

---

## INFO

1. [What You Need Before Starting](#what-you-need-before-starting)
2. [Step 1 — Install Docker](#step-1--install-docker)
3. [Step 2 — Create a Telegram Bot](#step-2--create-a-telegram-bot)
4. [Step 3 — Download the Project](#step-3--download-the-project)
5. [Step 4 — Configure the Bot](#step-4--configure-the-bot)
6. [Step 5 — Launch](#step-5--launch)
7. [Step 6 — Stop the Bot](#step-6--stop-the-bot)
8. [How to Play](#how-to-play)
9. [Managing Topics and Questions](#managing-topics-and-questions)
10. [Shop and Balance (Private Chat)](#shop-and-balance-private-chat)
11. [Configuration Reference](#configuration-reference)
12. [Development](#development)

---

## What You Need Before Starting

- A computer running **Linux**, **macOS**, or **Windows**
- An internet connection
- A Telegram account

No programming experience required — just follow the steps below! :D

---

## Step 1 — Install Docker

Docker runs the bot and its database inside isolated containers so you don't need to install Python or PostgreSQL on your machine. Only docker.

### Linux

Open a terminal and run these commands one by one (as root):

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Allow your user to run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
```

**Log out and log back in** for the group change to take effect, then verify:

```bash
docker --version
docker compose version
```

**Hello World from docker!**:

```bash
docker run hello-world
```

### macOS

1. Download **Docker Desktop** from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Open the downloaded `.dmg` file and drag Docker to Applications
3. Launch Docker Desktop from Applications and wait until the whale icon in the menu bar is steady
4. Open Terminal and verify:

```bash
docker --version
docker compose version
```

### Windows

1. Download **Docker Desktop** from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
2. Run the installer and **enable WSL 2** when prompted
3. Restart your computer if asked
4. Launch Docker Desktop and wait until it shows "Docker is running"
5. Open **PowerShell** and verify:

```powershell
docker --version
docker compose version
```

---

## Step 2 — Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a display name for your bot (e.g. `My Jeopardy Bot`)
4. Choose a username ending with `bot` (e.g. `my_jeopardy_game_bot`)
5. BotFather will reply with a **token** that looks like `123456789:ABCdefGHI-jklMNOpqrSTUvwxYZ`
6. **Copy this token** — you'll need it in the next step

---

## Step 3 — Download the Project

Open a terminal and clone the repository:

**HTTPS:**

```bash
git clone https://github.com/YOUR_USERNAME/SIGameBot.git
cd SIGameBot
```

**SSH:**

```bash
git clone git@github.com:YOUR_USERNAME/SIGameBot.git
cd SIGameBot
```

If you don't have Git installed:
- **Linux:** `sudo apt install git`
- **macOS:** `xcode-select --install`
- **Windows:** download from [https://git-scm.com/downloads](https://git-scm.com/downloads)

---

## Step 4 — Configure the Bot

Create your configuration file:

```bash
cp .env.example .env
```

Open `.env` in any text editor (Notepad, nano, VS Code — anything works) and paste your bot token:

```dotenv
BOT_TOKEN=123456789:ABCdefGHI-jklMNOpqrSTUvwxYZ
```

That's the only required setting. All other values have sensible defaults and can be left as-is. See [Configuration Reference](#configuration-reference) for details.

---

## Step 5 — Launch

From the project folder, run:

```bash
docker compose up --build -d
```

This will:
- Download the required images (first time only, may take a few minutes)
- Create the database and apply the schema automatically
- Start the bot

Check that everything is running:

```bash
docker compose ps -a
```

The bot container (`sigamebot-bot-1`) and the database (`sigamebot-db-1`) should show status `Up`. RabbitMQ and the optional admin API may also be running.

Check the bot logs to confirm it connected:

```bash
docker compose logs bot
```

Look for the line `Bot is running`.

---

## Step 6 — Stop the Bot

To stop:

```bash
docker compose down
```

To stop **and delete all game data** (reset the database):

```bash
docker compose down -v
```

To restart after stopping:

```bash
docker compose up -d
```

---

## How to Play

### Setting Up a Game

1. **Add the bot** to a Telegram group chat (use the bot's username to find it).
2. **Create a game** — any member sends `/start` in the group. That person becomes the **host**.
3. **Players join** using the **Войти** (Join) button; others can press **Смотреть** (Spectate) to watch.
4. The **host starts the game** with the **Старт** (Start) button or `/start_game` (at least 2 players required).

The lobby message shows **inline buttons in two columns** (readable on mobile):

- **Войти** · **Смотреть** — join as player or spectate  
- **Выйти** · **Счёт** — leave game, show score  
- **Правила** · **Справка** — open Rules and Help in a **private chat** with the bot  
- **Старт** · **Стоп** — start game, stop game (host)  
- **Магазин** — open Shop in private chat  
- **Управление в личке** — open bot DM for managing topics and questions  

### During the Game

1. A random player is chosen to pick the first question.
2. The bot shows a board with topics and point values; the current player taps a cell.
3. After the question is shown, everyone has **10 seconds** (configurable) to press **Звонок** (Buzzer).
4. The first to buzz has **15 seconds** (configurable) to type their answer in the chat.
5. **Correct** — player gets the points and chooses the next question.
6. **Wrong** — points are deducted, correct answer is shown, same player chooses again.
7. **No one buzzes** — correct answer is revealed, same player chooses again.
8. The game ends when all questions are played; the final scoreboard is shown.

### Commands in Group Chat

| Command | Description |
|--------|-------------|
| `/start` | Create a new game (you become host) |
| `/start_game` | Start the game (host only) |
| `/score` | Show current scoreboard |

Join, leave, spectate, start, stop, score, rules, help, and shop are also available as **inline buttons** under the lobby/game message. **Правила** and **Справка** open the bot in private chat to avoid spamming the group.

---

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

In a group, `/help` and `/rules` do not post the full text there — the bot asks you to open a private chat and use the **Правила** / **Справка** buttons or send the command in DM.

## Shop and Balance (Private Chat)

In private chat with the bot:

| Command | Description |
|--------|-------------|
| `/shop` | Open the in-game shop (categories and items) |
| `/balance` | Show your coin balance and daily reward info |

Use the **Магазин** button in the lobby to open the shop in private chat. Items can be used during the game (e.g. hints, double points).

---

## Configuration Reference

All settings go in the `.env` file. Only `BOT_TOKEN` is required.

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
| `QUESTION_SELECTION_TIMEOUT` | `30` | Seconds for the current player to choose a question |
| `BUZZER_TIMEOUT` | `10` | Seconds to wait for a buzzer press |
| `ANSWER_TIMEOUT` | `15` | Seconds to wait for an answer after buzzing |
| `LOG_LEVEL` | `INFO` | Log verbosity: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `logs/bot.log` | Log file path (auto-rotated at 10 MB) |
| `ADMIN_API_PORT` | `8000` | Port for the optional admin API (when running with docker compose) |

When using Docker, `DB_HOST`, `DB_PORT`, and RabbitMQ settings are applied by `docker-compose.yml`; you usually only set `BOT_TOKEN` and optionally the timeouts and log level.

---

## Development

Install all dependencies (prod + test tools):

```bash
pip install -r requirements/dev.txt
```

Lint the code:

```bash
ruff check .
```

Auto-fix lint issues:

```bash
ruff check --fix .
```

---

## License

MIT
