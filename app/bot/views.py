from __future__ import annotations

import bot.keyboards
import game.constants
import game.schemas


def render_many(
    responses: list[game.schemas.ServiceResponse],
) -> list[game.schemas.GameResponse]:
    return [render(response) for response in responses]


def render(response: game.schemas.ServiceResponse) -> game.schemas.GameResponse:
    view = response.view
    payload = response.payload

    if view == "game_created":
        username = payload["username"]
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"🎮 New game created by {username}!\n"
                "Use /join to play or /spectate to watch."
            ),
            keyboard=bot.keyboards.lobby(),
        )
    if view == "player_joined":
        username = payload["username"]
        player_names = payload["player_names"]
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"👋 {username} joined!\nPlayers ({len(player_names)}): "
                + ", ".join(player_names)
            ),
        )
    if view == "player_rejoined":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"👋 {payload['username']} rejoined the game!",
        )
    if view == "now_spectating":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"👀 {payload['username']} is now spectating.",
        )
    if view == "left_game":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"🚪 {payload['username']} left the game.",
        )
    if view == "host_transferred":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"🚪 {payload['old_host']} (host) left.\n"
                f"👑 {payload['new_host']} is the new host!"
            ),
        )
    if view == "scoreboard":
        lines = [payload["title"]]
        for rank, (name, points) in enumerate(payload["scores"], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
            lines.append(f"{medal} {name}: {points}")
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="\n".join(lines),
            keyboard=bot.keyboards.score() if payload.get("with_controls") else None,
        )
    if view == "board":
        rows = payload["rows"]
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"{payload['intro']}\n\n"
                f"{payload['current_player']}, choose a question:\n\n"
                f"{bot.keyboards.board_text(rows)}"
            ).strip(),
            keyboard=bot.keyboards.board(rows),
        )
    if view == "question_asked":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"📝 [{payload['topic']}] for {payload['cost']} points:\n\n"
                f"{payload['text']}\n\n⏱ {payload['buzzer_timeout']}s to buzz!"
            ),
            keyboard=bot.keyboards.buzzer(),
        )
    if view == "buzzer_pressed":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"🔔 {payload['username']} pressed the buzzer!\n"
                f"You have {payload['answer_timeout']} seconds to answer.\n"
                "Use /answer <your answer>"
            ),
        )
    if view == "answer_correct":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"✅ Correct! {payload['username']} gets {payload['cost']} "
                f"points!\nAnswer: {payload['correct_answer']}"
            ),
        )
    if view == "answer_wrong":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                f"❌ Wrong! {payload['username']} loses {payload['cost']} "
                f"points.\nCorrect answer: {payload['correct_answer']}"
            ),
        )
    if view == "buzzer_timeout":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                "⏰ Time's up! No one pressed the buzzer.\n"
                f"Correct answer: {payload['correct_answer']}"
            ),
        )
    if view == "answer_timeout":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=(
                "⏰ Time's up! "
                f"{payload['username']} didn't answer in time. "
                f"−{payload['cost']} points.\n"
                f"Correct answer: {payload['correct_answer']}"
            ),
        )
    if view == "topic_select_for_add":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Select a topic for the new question:",
            keyboard=bot.keyboards.topic_select_for_add(payload["topics"]),
        )
    if view == "topic_select_for_delete":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Select a topic to delete (all its questions will be removed):",
            keyboard=bot.keyboards.topic_select_for_delete(
                payload["topics_with_counts"]
            ),
        )
    if view == "topic_select_for_delete_question":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Select a topic to browse questions for deletion:",
            keyboard=bot.keyboards.topic_select_for_delete_question(
                payload["topics_with_counts"]
            ),
        )
    if view == "question_select_for_delete":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Select a question to delete:",
            keyboard=bot.keyboards.question_select_for_delete(
                payload["questions"]
            ),
        )
    if view == "help":
        help_text = (
            "📋 Available commands:\n\n"
            "🎮 Game Management:\n"
            "/start — Create a new game\n"
            "/join — Join as a player\n"
            "/spectate — Watch the game\n"
            "/leave — Leave the game\n"
            "/start_game — Start the game (host)\n"
            "/stop — Stop the game (host)\n"
            "/score — Show current scores\n\n"
            "📝 Content Management (private chat):\n"
            "/add_topic <name> — Create a topic\n"
            "/add_question — Add a question\n"
            "/delete_topic — Delete a topic\n"
            "/delete_question — Delete a question\n\n"
            "ℹ️ Info:\n"
            "/rules — Game rules\n"
            "/help — This message\n"
            "/my_games — Your hosted games"
        )
        return game.schemas.GameResponse(chat_id=response.chat_id, text=help_text)
    if view == "rules":
        rules_text = (
            "📖 Jeopardy Game Rules:\n\n"
            "1. The host creates a game with /start\n"
            "2. Players join with /join\n"
            "3. The host starts the game with /start_game\n"
            "4. A random player is chosen to pick a question\n"
            "5. A question is shown from the board\n"
            f"6. Players have {payload['buzzer_timeout']}s to press the buzzer\n"
            f"7. The first to buzz has {payload['answer_timeout']}s to answer "
            "with /answer <text>\n"
            "8. Correct answer: +points, you pick next question\n"
            "9. Wrong answer: −points, question is burned\n"
            "10. Game ends when all questions are answered\n\n"
            "🏆 Player with the most points wins!"
        )
        return game.schemas.GameResponse(chat_id=response.chat_id, text=rules_text)
    if view == "plain":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=payload["text"],
        )
    if view == "no_active_game":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="No active game. Use /start to create one.",
        )
    if view == "no_active_game_here":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="No active game in this chat.",
        )
    if view == "game_already_running":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="A game is already running in this chat.",
        )
    if view == "game_already_started":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Game already started. Wait for the next round.",
        )
    if view == "game_in_progress":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Game is already in progress.",
        )
    if view == "only_host":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Only the host can do this action.",
        )
    if view == "need_two_players":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Need at least 2 players to start.",
        )
    if view == "no_questions":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="No questions in the database. Add some first!",
        )
    if view == "not_your_turn":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="It's not your turn to choose a question.",
        )
    if view == "already_in_game":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"{payload['username']}, you are already in the game.",
        )
    if view == "already_spectating":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"{payload['username']}, you are already spectating.",
        )
    if view == "not_in_game":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=f"{payload['username']}, you are not in the game.",
        )
    if view == "dialog_prompt_topic":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Enter the topic name:",
        )
    if view == "dialog_prompt_question":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="Send the question text:",
        )
    if view == "dialog_cancelled":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="OK, cancelled.",
        )
    if view == "dialog_done":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text="OK, done.",
        )
    if view == "db_error":
        return game.schemas.GameResponse(
            chat_id=response.chat_id,
            text=game.constants.BotMessage.DB_ERROR,
        )

    return game.schemas.GameResponse(
        chat_id=response.chat_id,
        text="Unexpected response.",
    )
