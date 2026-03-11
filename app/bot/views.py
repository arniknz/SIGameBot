from __future__ import annotations

import collections.abc
import typing

import bot.keyboards
import game.constants
import game.schemas

type _P = dict[str, typing.Any]

_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

Renderer = collections.abc.Callable[[int, _P], game.schemas.GameResponse]


def render_many(
    responses: list[game.schemas.ServiceResponse],
) -> list[game.schemas.GameResponse]:
    return [render(response) for response in responses]


def _make(
    chat_id: int,
    text: str,
    keyboard: list[list[dict[str, str]]] | None = None,
) -> game.schemas.GameResponse:
    return game.schemas.GameResponse(
        chat_id=chat_id, text=text, keyboard=keyboard
    )


def _render_game_created(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    kb = bot.keyboards.lobby()
    bot_username = p.get("bot_username")
    if bot_username:
        kb.append(bot.keyboards.dm_bot_button(bot_username))
    return _make(
        cid,
        (
            f"🎲 Let the games begin!\n\n"
            f"🎮 {p['username']} created a new game!\n"
            f"Press Join to play or Spectate to watch.\n\n"
            f"🕹 Waiting for players..."
        ),
        keyboard=kb,
    )


def _render_player_joined(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    names = p["player_names"]
    return _make(
        cid,
        (
            f"🎉 {p['username']} joined the game!\n\n"
            f"👥 Players ({len(names)}): " + ", ".join(names)
        ),
    )


def _render_player_rejoined(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"🔄 Welcome back, {p['username']}! Ready to play again?",
    )


def _render_now_spectating(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"👀 {p['username']} is watching the game. Enjoy the show!",
    )


def _render_left_game(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"👋 {p['username']} has left the game. See you next time!",
    )


def _render_host_transferred(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"👋 {p['old_host']} (host) has left.\n"
            f"👑 {p['new_host']} is the new host! "
            f"Long live the host!"
        ),
    )


def _render_scoreboard(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    lines = [p["title"]]
    for rank, (name, points) in enumerate(p["scores"], 1):
        medal = _MEDAL.get(rank, f"{rank}.")
        lines.append(f"{medal} {name}: {points} pts")
    keyboard = (
        bot.keyboards.score() if p.get("with_controls") else None
    )
    return _make(cid, "\n".join(lines), keyboard=keyboard)


def _render_board(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    rows = p["rows"]
    intro = p["intro"]
    player = p["current_player"]
    timeout = p.get("selection_timeout")
    board_text = bot.keyboards.board_text(rows)
    parts = []
    if intro:
        parts.append(intro)
    turn_msg = f"🎤 {player}, it's your turn! Pick a question"
    if timeout:
        turn_msg += f" (⏱ {timeout}s):"
    else:
        turn_msg += ":"
    parts.append(turn_msg + "\n")
    parts.append(board_text)
    return _make(
        cid,
        "\n\n".join(parts),
        keyboard=bot.keyboards.board(rows),
    )


def _render_question_asked(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"📢 Category: {p['topic']}\n"
            f"💰 Worth: {p['cost']} points\n\n"
            f"❓ {p['text']}\n\n"
            f"⏱ {p['buzzer_timeout']}s — hit the buzzer!"
        ),
        keyboard=bot.keyboards.buzzer(),
    )


def _render_buzzer_pressed(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⚡ {p['username']} hit the buzzer!\n\n"
            f"⏱ You have {p['answer_timeout']}s to answer.\n"
            f"Type your answer now!"
        ),
    )


def _render_answer_correct(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"🎯 CORRECT! Brilliant!\n\n"
            f"🌟 {p['username']} earns "
            f"+{p['cost']} points!\n"
            f"✅ Answer: {p['correct_answer']}"
        ),
    )


def _render_answer_wrong(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"💔 Ouch! Wrong answer.\n\n"
            f"📉 {p['username']} loses "
            f"−{p['cost']} points.\n"
            f"✅ Correct answer: {p['correct_answer']}"
        ),
    )


def _render_buzzer_timeout(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"💤 Time's up! Nobody buzzed in.\n\n"
            f"✅ The answer was: {p['correct_answer']}"
        ),
    )


def _render_answer_timeout(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⏰ Too slow! Time ran out.\n\n"
            f"📉 {p['username']} loses "
            f"−{p['cost']} points.\n"
            f"✅ Correct answer: {p['correct_answer']}"
        ),
    )


def _render_choosing_timeout(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⏰ {p['old_player']} took too long "
            f"to choose a question!\n"
            f"🔄 Skipping to the next player..."
        ),
    )


def _render_topic_select_for_add(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "📂 Pick a topic for your new question:",
        keyboard=bot.keyboards.topic_select_for_add(p["topics"]),
    )


def _render_topic_select_for_delete(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "🗑 Select a topic to delete (all questions will be removed):",
        keyboard=bot.keyboards.topic_select_for_delete(
            p["topics_with_counts"]
        ),
    )


def _render_topic_select_for_delete_question(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "📂 Choose a topic to browse questions for deletion:",
        keyboard=bot.keyboards.topic_select_for_delete_question(
            p["topics_with_counts"]
        ),
    )


def _render_question_select_for_delete(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "🗑 Pick a question to delete:",
        keyboard=bot.keyboards.question_select_for_delete(
            p["questions"]
        ),
    )


def _render_help(
    cid: int, _p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            "📋 Available Commands\n\n"
            "🏠 Group Chat Commands:\n"
            "  /start — Create a new game\n"
            "  /join — Join as a player\n"
            "  /spectate — Watch the game\n"
            "  /leave — Leave the game\n"
            "  /start_game — Start the game (host)\n"
            "  /stop — Stop the game (host)\n"
            "  /score — Show current scores\n\n"
            "💬 Private Chat Commands:\n"
            "  /my_games — Your hosted games\n"
            "  /add_topic <name> — Create a topic\n"
            "  /add_question — Add a question\n"
            "  /delete_topic — Delete a topic\n"
            "  /delete_question — Delete a question\n\n"
            "ℹ️ Available Everywhere:\n"
            "  /help — This message\n"
            "  /rules — Game rules"
        ),
    )


def _render_rules(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            "📖 Jeopardy Game Rules\n\n"
            "1️⃣ The host creates a game with /start\n"
            "2️⃣ Players join with /join\n"
            "3️⃣ Host starts the game with /start_game\n"
            "4️⃣ A random player picks a question "
            "from the board\n"
            "5️⃣ The question appears for everyone\n"
            f"6️⃣ Players have "
            f"{p['buzzer_timeout']}s to press 🔔 Buzzer\n"
            f"7️⃣ First to buzz gets "
            f"{p['answer_timeout']}s to answer\n"
            "8️⃣ ✅ Correct → +points, "
            "you pick next question\n"
            "9️⃣ ❌ Wrong → −points, "
            "question is burned\n"
            "🔟 Game ends when all questions "
            "are answered\n\n"
            "🏆 Player with the most points wins!"
        ),
    )


def _render_my_games(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    games = p["games"]
    lines = ["🎮 Your Active Games\n"]
    status_icons = {"waiting": "⏳", "active": "🎯"}
    for i, g in enumerate(games, 1):
        icon = status_icons.get(g["status"], "❓")
        lines.append(
            f"{i}. {icon} {g['status'].title()}"
            f" | 👥 {g['player_count']} player(s)"
            f" | 📅 {g['created_at']}"
        )
    kb = bot.keyboards.my_games_jump_buttons(games)
    return _make(cid, "\n".join(lines), keyboard=kb or None)


def _render_private_only_command(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    bot_username = p.get("bot_username", "")
    text = "❌ This command only works in private chat with me."
    kb: list[list[dict[str, str]]] | None = None
    if bot_username:
        text += f" DM me: @{bot_username}"
        kb = [
            [
                {
                    "text": "📩 Open DM",
                    "url": f"https://t.me/{bot_username}",
                }
            ]
        ]
    return _make(cid, text, keyboard=kb)


_SIMPLE_VIEWS: dict[game.constants.ViewName, str] = {
    game.constants.ViewName.NO_ACTIVE_GAME: (
        "🎮 No active game here. Use /start to create one!"
    ),
    game.constants.ViewName.NO_ACTIVE_GAME_HERE: (
        "🤷 No active game in this chat."
    ),
    game.constants.ViewName.GAME_ALREADY_RUNNING: (
        "⚠️ A game is already running in this chat!"
    ),
    game.constants.ViewName.GAME_ALREADY_STARTED: (
        "⏳ Game already started. Wait for the next round!"
    ),
    game.constants.ViewName.GAME_IN_PROGRESS: (
        "🕹 Game is already in progress!"
    ),
    game.constants.ViewName.ONLY_HOST: (
        "🚫 Only the host can do this action."
    ),
    game.constants.ViewName.NEED_TWO_PLAYERS: (
        "👥 Need at least 2 players to start. Invite more friends!"
    ),
    game.constants.ViewName.NO_QUESTIONS: (
        "📭 No questions in the database. Add some first!"
    ),
    game.constants.ViewName.NOT_YOUR_TURN: (
        "🙅 It's not your turn to choose a question."
    ),
    game.constants.ViewName.DIALOG_PROMPT_TOPIC: (
        "📝 Enter the topic name:"
    ),
    game.constants.ViewName.DIALOG_PROMPT_QUESTION: (
        "✏️ Send the question text:"
    ),
    game.constants.ViewName.DIALOG_PROMPT_ANSWER: (
        "💡 Now send the correct answer:"
    ),
    game.constants.ViewName.DIALOG_PROMPT_COST: (
        "💰 Enter the point cost (e.g. 100, 200, 500):"
    ),
    game.constants.ViewName.DIALOG_CANCELLED: "❌ Cancelled.",
    game.constants.ViewName.DIALOG_DONE: "✅ Done!",
    game.constants.ViewName.DB_ERROR: (
        game.constants.BotMessage.DB_ERROR
    ),
    game.constants.ViewName.GAME_ENDED_NO_PLAYERS: (
        "🏚 No players remain — game ended."
    ),
    game.constants.ViewName.UNKNOWN_COMMAND: (
        "🤔 Unknown command. Use /help to see what I can do!"
    ),
    game.constants.ViewName.GROUP_ONLY_COMMAND: (
        "❌ This command only works in group chats. "
        "Add me to a group to play!"
    ),
}


def _render_simple_with_username(
    cid: int, p: _P, template: str
) -> game.schemas.GameResponse:
    return _make(cid, template.format(username=p["username"]))


_USERNAME_VIEWS: dict[game.constants.ViewName, str] = {
    game.constants.ViewName.ALREADY_IN_GAME: (
        "ℹ️ {username}, you're already in the game!"
    ),
    game.constants.ViewName.ALREADY_SPECTATING: (
        "ℹ️ {username}, you're already spectating!"
    ),
    game.constants.ViewName.NOT_IN_GAME: (
        "🤔 {username}, you're not in this game."
    ),
}


_RENDERERS: dict[game.constants.ViewName, Renderer] = {
    game.constants.ViewName.GAME_CREATED: _render_game_created,
    game.constants.ViewName.PLAYER_JOINED: _render_player_joined,
    game.constants.ViewName.PLAYER_REJOINED: _render_player_rejoined,
    game.constants.ViewName.NOW_SPECTATING: _render_now_spectating,
    game.constants.ViewName.LEFT_GAME: _render_left_game,
    game.constants.ViewName.HOST_TRANSFERRED: _render_host_transferred,
    game.constants.ViewName.SCOREBOARD: _render_scoreboard,
    game.constants.ViewName.BOARD: _render_board,
    game.constants.ViewName.QUESTION_ASKED: _render_question_asked,
    game.constants.ViewName.BUZZER_PRESSED: _render_buzzer_pressed,
    game.constants.ViewName.ANSWER_CORRECT: _render_answer_correct,
    game.constants.ViewName.ANSWER_WRONG: _render_answer_wrong,
    game.constants.ViewName.BUZZER_TIMEOUT: _render_buzzer_timeout,
    game.constants.ViewName.ANSWER_TIMEOUT: _render_answer_timeout,
    game.constants.ViewName.CHOOSING_TIMEOUT: _render_choosing_timeout,
    game.constants.ViewName.TOPIC_SELECT_FOR_ADD: (
        _render_topic_select_for_add
    ),
    game.constants.ViewName.TOPIC_SELECT_FOR_DELETE: (
        _render_topic_select_for_delete
    ),
    game.constants.ViewName.TOPIC_SELECT_FOR_DELETE_QUESTION: (
        _render_topic_select_for_delete_question
    ),
    game.constants.ViewName.QUESTION_SELECT_FOR_DELETE: (
        _render_question_select_for_delete
    ),
    game.constants.ViewName.HELP: _render_help,
    game.constants.ViewName.RULES: _render_rules,
    game.constants.ViewName.MY_GAMES: _render_my_games,
    game.constants.ViewName.PRIVATE_ONLY_COMMAND: (
        _render_private_only_command
    ),
}


def render(
    response: game.schemas.ServiceResponse,
) -> game.schemas.GameResponse:
    view = response.view
    p = response.payload
    cid = response.chat_id

    renderer = _RENDERERS.get(view)
    if renderer is not None:
        return renderer(cid, p)

    if view == game.constants.ViewName.PLAIN:
        return _make(cid, p["text"])

    simple_text = _SIMPLE_VIEWS.get(view)
    if simple_text is not None:
        return _make(cid, simple_text)

    username_template = _USERNAME_VIEWS.get(view)
    if username_template is not None:
        return _render_simple_with_username(
            cid, p, username_template
        )

    return _make(cid, "⚠️ Something unexpected happened.")
