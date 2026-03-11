# SIGameBot

Multiplayer Jeopardy (SI Game) bot for Telegram group chats.

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
10. [Configuration Reference](#configuration-reference)
11. [Development](#development)

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

You should see two containers with status `Up`:

```
NAME              STATUS
sigamebot-db-1    Up
sigamebot-bot-1   Up
```

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

1. **Add the bot** to a Telegram group chat (use the bot's username to find it)
2. **Create a game** — any member sends `/start` in the group. That person becomes the **host**
3. **Players join** by pressing the **Join** button. Others can press **Spectate** to watch
4. The **host starts the game** by sending `/start_game` (at least 2 players required)

### During the Game

1. A random player is selected to pick the first question
2. The bot shows a board with topics and point values — the current player taps a question
3. The question appears — all players have **10 (10 is default value, you can change it in .env) seconds** to press the **Buzzer** button
4. The first player to buzz in has **15 (15 is default value, you can change it in .env) seconds** to type their answer directly in chat
5. **Correct answer** — player earns the points and picks the next question
6. **Wrong answer** — points are deducted, the correct answer is shown, the same player picks again
7. **No one buzzes in** — correct answer is revealed, same player picks again
8. The game ends when all questions have been played, and the final scoreboard is shown

### Commands in Group Chat

| Command | Description |
|---|---|
| `/start` | Create a new game (you become host) |
| `/start_game` | Start the game (host only) |
| `/score` | Show current scoreboard |

All other actions (join, leave, spectate, stop, buzzer, help, rules) are **inline buttons** — no need to type commands.

---

## Managing Topics and Questions

Before playing, you need to add topics and questions. This is done in a **private chat** with the bot (message the bot directly, not in the group).

| Command | What it does |
|---|---|
| `/add_topic` | Create a new topic (bot will ask for a name) |
| `/add_question` | Add a question (bot guides you step by step: pick topic, enter question, answer, and point cost) |
| `/delete_topic` | Delete a topic and all its questions |
| `/delete_question` | Delete a single question |
| `/my_games` | Show games where you are host |
| `/help` | List all commands |
| `/rules` | Show game rules |
| `/cancel` | Cancel current action |

---

## Configuration Reference

All settings go in the `.env` file. Only `BOT_TOKEN` is required.

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Your Telegram bot token from BotFather |
| `DB_HOST` | `localhost` | PostgreSQL host (do not change for Docker) |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `sigamebot` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | `postgres` | Database password |
| `WORKERS_COUNT` | `3` | Number of concurrent update workers |
| `BUZZER_TIMEOUT` | `10` | Seconds to wait for a buzzer press |
| `ANSWER_TIMEOUT` | `15` | Seconds to wait for an answer after buzzing |
| `LOG_LEVEL` | `INFO` | Log verbosity: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `logs/bot.log` | Log file path (auto-rotated at 10 MB) |

When using Docker, `DB_HOST` and `DB_PORT` are set automatically by `docker-compose.yml` — you don't need to touch them.

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
