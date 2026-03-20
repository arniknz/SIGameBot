from __future__ import annotations

import collections.abc
import typing

import bot.keyboards
import game.constants
import game.schemas
import game.shop_items

_P = dict[str, typing.Any]

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


def _render_game_created(cid: int, p: _P) -> game.schemas.GameResponse:
    bot_username = p.get("bot_username", "")
    username = p.get("username", "")
    kb = bot.keyboards.lobby(bot_username)
    return _make(
        cid,
        (
            f"🎲 Игра начинается!\n\n"
            f"🎮 {username} создал(а) новую игру!\n"
            "Нажмите «Войти», чтобы играть, или «Смотреть» — "
            "чтобы наблюдать.\n\n"
            f"🕹 Ожидаем игроков..."
        ),
        keyboard=kb,
    )


def _render_lobby(cid: int, p: _P) -> game.schemas.GameResponse:
    roster = p["roster"]
    bot_username = p.get("bot_username", "")

    players = [
        (name, is_host)
        for name, role, is_host in roster
        if role == game.constants.ParticipantRole.PLAYER
    ]
    spectators = [
        name
        for name, role, _is_host in roster
        if role == game.constants.ParticipantRole.SPECTATOR
    ]

    lines = ["🎲 Игра «Своя игра»\n"]
    lines.append(f"👥 Игроки ({len(players)}):")
    for name, is_host in players:
        tag = "👑" if is_host else "🎯"
        suffix = " (ведущий)" if is_host else ""
        lines.append(f"  {tag} {name}{suffix}")

    if spectators:
        lines.append(f"\n👀 Зрители ({len(spectators)}):")
        lines.extend(f"  👀 {name}" for name in spectators)

    if len(players) < 2:
        lines.append("\n⏳ Нужно минимум 2 игрока для старта.")
    else:
        lines.append("\n🕹 Можно начинать! Ведущий нажимает «Начать игру».")

    kb = bot.keyboards.lobby(bot_username)
    return _make(cid, "\n".join(lines), keyboard=kb)


def _render_player_joined(cid: int, p: _P) -> game.schemas.GameResponse:
    player_names = p.get("player_names", [])
    return _make(
        cid,
        (
            f"🎉 {p['username']} присоединился(ась) к игре!\n\n"
            f"👥 Игроки ({len(player_names)}): " + ", ".join(player_names)
        ),
    )


def _render_player_rejoined(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"🔄 С возвращением, {p['username']}! Готовы играть снова?",
    )


def _render_now_spectating(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"👀 {p['username']} смотрит игру. Приятного просмотра!",
    )


def _render_left_game(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        f"👋 {p['username']} вышел(а) из игры. До встречи!",
    )


def _render_host_transferred(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"👋 {p['old_host']} (ведущий) вышел(а).\n"
            f"👑 Новый ведущий — {p['new_host']}! "
            f"Да здравствует ведущий!"
        ),
    )


def _render_scoreboard(cid: int, p: _P) -> game.schemas.GameResponse:
    lines = [p["title"]]
    for rank, (name, points) in enumerate(p["scores"], 1):
        medal = _MEDAL.get(rank, f"{rank}.")
        lines.append(f"{medal} {name}: {points} очк.")
    keyboard = bot.keyboards.score() if p.get("with_controls") else None
    return _make(cid, "\n".join(lines), keyboard=keyboard)


def _render_board(cid: int, p: _P) -> game.schemas.GameResponse:
    rows = p["rows"]
    intro = p["intro"]
    player = p["current_player"]
    timeout = p.get("selection_timeout")
    board_text = bot.keyboards.board_text(rows)
    parts = []
    if intro:
        parts.append(intro)
    turn_msg = f"🎤 {player}, ваша очередь! Выберите вопрос"
    if timeout:
        turn_msg += f" (⏱ {timeout} сек):"
    else:
        turn_msg += ":"
    parts.append(turn_msg + "\n")
    parts.append(board_text)
    return _make(
        cid,
        "\n\n".join(parts),
        keyboard=bot.keyboards.board(rows),
    )


def _render_question_asked(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"📢 Категория: {p['topic']}\n"
            f"💰 Стоимость: {p['cost']} очков\n\n"
            f"❓ {p['text']}\n\n"
            f"⏱ {p['buzzer_timeout']} сек — нажмите кнопку «Звонок»!"
        ),
        keyboard=bot.keyboards.buzzer(),
    )


def _render_cat_revealed(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"🎲 Кот в мешке!\n\n"
            f"📢 Категория: {p['topic']}\n"
            f"💰 Стоимость: {p['cost']} очков\n\n"
            f"❓ {p['text']}\n\n"
            f"⏱ {p['buzzer_timeout']} сек — нажмите кнопку «Звонок»!"
        ),
        keyboard=bot.keyboards.buzzer(),
    )


def _render_buzzer_pressed(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⚡ {p['username']} нажал(а) звонок!\n\n"
            f"⏱ У вас {p['answer_timeout']} сек на ответ.\n"
            f"Введите ответ!"
        ),
        keyboard=bot.keyboards.answer_prompt(
            show_all_in=bool(p.get("show_all_in")),
        ),
    )


def _render_all_in_activated(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⚡ {p['username']} идёт ва-банк!\n\n"
            f"🎯 Верный ответ → УДВОЕНИЕ очков (+{p['cost'] * 2})!\n"
            f"💀 Неверный ответ → счёт обнуляется!\n\n"
            f"⏱ Введите ответ!"
        ),
    )


def _render_answer_correct(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"🎯 ВЕРНО! Отлично!\n\n"
            f"🌟 {p['username']} получает "
            f"+{p['cost']} очков!\n"
            f"✅ Ответ: {p['correct_answer']}"
        ),
    )


def _render_answer_wrong(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"💔 Увы! Неверный ответ.\n\n"
            f"📉 {p['username']} теряет "
            f"−{p['cost']} очков.\n"
            f"✅ Правильный ответ: {p['correct_answer']}"
        ),
    )


def _render_buzzer_timeout(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"💤 Время вышло! Никто не нажал звонок.\n\n"
            f"✅ Правильный ответ: {p['correct_answer']}"
        ),
    )


def _render_answer_timeout(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⏰ Слишком медленно! Время вышло.\n\n"
            f"📉 {p['username']} теряет "
            f"−{p['cost']} очков.\n"
            f"✅ Правильный ответ: {p['correct_answer']}"
        ),
    )


def _render_choosing_timeout(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"⏰ {p['old_player']} слишком долго "
            f"выбирал(а) вопрос!\n"
            f"🔄 Переход к следующему игроку..."
        ),
    )


def _render_game_ended_no_players(
    cid: int, _p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            "\U0001f3c1 Игра завершена. Игроков не осталось.\n\n"
            "Чтобы создать новую игру, отправьте /start"
        ),
        keyboard=[],
    )


def _render_game_ended_afk(cid: int, p: _P) -> game.schemas.GameResponse:
    count = p["failed_count"]
    return _make(
        cid,
        (
            f"💤 {count} ходов подряд без выбора вопроса.\n"
            f"🏚 Похоже, все игроки не у дел — завершаем игру."
        ),
    )


def _render_topic_select_for_add(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        "📂 Выберите тему для нового вопроса:",
        keyboard=bot.keyboards.topic_select_for_add(p["topics"]),
    )


def _render_topic_select_for_delete(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "🗑 Выберите тему для удаления (все вопросы будут скрыты):",
        keyboard=bot.keyboards.topic_select_for_delete(p["topics_with_counts"]),
    )


def _render_topic_select_for_delete_question(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "📂 Выберите тему, чтобы просмотреть вопросы для удаления:",
        keyboard=bot.keyboards.topic_select_for_delete_question(
            p["topics_with_counts"]
        ),
    )


def _render_question_select_for_delete(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "🗑 Выберите вопрос для удаления:",
        keyboard=bot.keyboards.question_select_for_delete(p["questions"]),
    )


def _render_topic_select_for_restore(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "♻️ Выберите тему для восстановления:",
        keyboard=bot.keyboards.topic_select_for_restore(p["topics"]),
    )


def _render_question_select_for_restore(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        "♻️ Выберите вопрос для восстановления:",
        keyboard=bot.keyboards.question_select_for_restore(p["questions"]),
    )


def _render_help(cid: int, _p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            "📋 Доступные команды\n\n"
            "🏠 В групповом чате:\n"
            "  /start — Создать новую игру\n"
            "  /join — Войти в игру игроком\n"
            "  /spectate — Смотреть игру\n"
            "  /leave — Выйти из игры\n"
            "  /start_game — Начать игру (ведущий)\n"
            "  /stop — Остановить игру (ведущий)\n"
            "  /score — Показать счёт\n\n"
            "💬 В личке с ботом:\n"
            "  /my_games — Ваши игры\n"
            "  /my_content — Ваши темы и вопросы\n"
            "  /add_topic <название> — Создать тему\n"
            "  /add_question — Добавить вопрос\n"
            "  /delete_topic — Скрыть тему\n"
            "  /delete_question — Скрыть вопрос\n"
            "  /restore_topic — Восстановить тему\n"
            "  /restore_question — Восстановить вопрос\n"
            "  /upload_csv — Загрузить вопросы из CSV\n"
            "  /shop — Магазин предметов\n"
            "  /balance — Ваш баланс\n\n"
            "ℹ️ Везде:\n"
            "  /help — Это сообщение\n"
            "  /rules — Правила игры\n\n"
            "🎲 Особые механики:\n"
            "  🎲 Кот в мешке — случайный вопрос "
            "из любой темы по неожиданной стоимости\n"
            "  ⚡ Ва-банк — удвоение очков за верный ответ "
            "или обнуление за ошибку (раз за игру, для отстающих)"
        ),
    )


def _render_rules(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            "📖 Правила игры «Своя игра»\n\n"
            "1️⃣ Ведущий создаёт игру командой /start\n"
            "2️⃣ Игроки входят командой /join\n"
            "3️⃣ Ведущий начинает игру командой /start_game\n"
            "4️⃣ Случайный игрок выбирает вопрос "
            "на табло\n"
            "5️⃣ Вопрос показывается всем\n"
            f"6️⃣ У игроков "
            f"{p['buzzer_timeout']} сек, чтобы нажать 🔔 Звонок\n"
            f"7️⃣ Первый нажавший получает "
            f"{p['answer_timeout']} сек на ответ\n"
            "8️⃣ ✅ Верно → +очки, "
            "выбираете следующий вопрос\n"
            "9️⃣ ❌ Неверно → −очки, "
            "вопрос сгорает\n"
            "🔟 Игра заканчивается, когда все вопросы "
            "отыграны\n\n"
            "🎲 Кот в мешке — нажмите загадочную кнопку "
            "на табло, чтобы получить случайный вопрос "
            "из любой темы по неожиданной стоимости!\n\n"
            "⚡ Ва-банк — если очков меньше половины от лидера, "
            "после нажатия звонка можно идти ва-банк: "
            "верно = удвоение очков, неверно = счёт обнуляется! "
            "Раз за игру.\n\n"
            "🏆 Побеждает игрок с наибольшим количеством очков!"
        ),
    )


def _render_my_games(cid: int, p: _P) -> game.schemas.GameResponse:
    games = p["games"]
    lines = ["🎮 Ваши активные игры\n"]
    for i, g in enumerate(games, 1):
        status_str = g["status"]
        try:
            status_enum = game.constants.GameStatus(status_str)
        except ValueError:
            status_enum = None
        default_icon = game.constants.DEFAULT_STATUS_ICON
        icon = (
            game.constants.GAME_STATUS_ICON.get(status_enum, default_icon)
            if status_enum
            else default_icon
        )
        label = (
            game.constants.GAME_STATUS_LABEL.get(status_enum, status_str)
            if status_enum
            else status_str
        )
        lines.append(
            f"{i}. {icon} {label}"
            f" | 👥 {g['player_count']} игрок(ов)"
            f" | 📅 {g['created_at']}"
        )
    kb = bot.keyboards.my_games_jump_buttons(games)
    return _make(cid, "\n".join(lines), keyboard=kb or None)


def _render_private_only_command(cid: int, p: _P) -> game.schemas.GameResponse:
    bot_username = p.get("bot_username", "")
    text = "❌ Эта команда работает только в личке со мной."
    kb: list[list[dict[str, str]]] | None = None
    if bot_username:
        text += f" Напишите мне: @{bot_username}"
        kb = [
            [
                {
                    "text": "📩 Открыть личку",
                    "url": f"https://t.me/{bot_username}",
                }
            ]
        ]
    return _make(cid, text, keyboard=kb)


def _render_shop_redirect(cid: int, p: _P) -> game.schemas.GameResponse:
    bot_username = p.get("bot_username", "")
    return _make(
        cid,
        "🛒 Откройте магазин в личке со мной, чтобы просмотреть товары!",
        keyboard=bot.keyboards.shop_redirect_button(bot_username)
        if bot_username
        else None,
    )


def _render_shop_main(cid: int, p: _P) -> game.schemas.GameResponse:
    balance = p["balance"]
    item_count = p.get("item_count", 0)
    return _make(
        cid,
        (
            f"🛒 Добро пожаловать в магазин!\n\n"
            f"💰 Ваш баланс: {balance} очк.\n"
            f"📦 Предметов в инвентаре: {item_count}\n\n"
            f"Выберите категорию:"
        ),
        keyboard=bot.keyboards.shop_main(),
    )


def _render_shop_category(cid: int, p: _P) -> game.schemas.GameResponse:
    category = p["category"]
    items = p["items"]
    balance = p["balance"]
    label = game.shop_items.CATEGORY_LABELS.get(category, str(category).title())

    lines = [f"{label}\n"]
    lines.extend(
        f"{item.emoji} {item.name} — {item.price}💰\n    {item.description}"
        for item in items
    )
    lines.append(f"\n💰 Ваш баланс: {balance} очк.")

    return _make(
        cid,
        "\n".join(lines),
        keyboard=bot.keyboards.shop_category(items, balance),
    )


def _render_shop_buy_ok(cid: int, p: _P) -> game.schemas.GameResponse:
    item = p["item"]
    new_balance = p["new_balance"]
    return _make(
        cid,
        (
            f"✅ Куплено: {item.emoji} {item.name}!\n\n"
            f"💰 Остаток: {new_balance} очк."
        ),
        keyboard=bot.keyboards.shop_main(),
    )


def _render_shop_insufficient(cid: int, p: _P) -> game.schemas.GameResponse:
    item = p["item"]
    balance = p["balance"]
    return _make(
        cid,
        (
            f"❌ Недостаточно очков!\n\n"
            f"{item.emoji} {item.name} стоит {item.price}💰\n"
            f"💰 Ваш баланс: {balance} очк.\n"
            f"📉 Нужно ещё {item.price - balance} очк."
        ),
        keyboard=bot.keyboards.shop_main(),
    )


def _render_inventory_list(cid: int, p: _P) -> game.schemas.GameResponse:
    items = p["items"]
    remaining = p.get("remaining_seconds", 0)
    lines = [f"📦 Ваш инвентарь (⏱ осталось {remaining} сек)\n"]
    for item in items:
        count = f" x{item['count']}" if item["count"] > 1 else ""
        lines.append(
            f"{item['emoji']} {item['name']}{count} — {item['description']}"
        )
    lines.append("\nНажмите на предмет, чтобы использовать:")
    return _make(
        cid,
        "\n".join(lines),
        keyboard=bot.keyboards.inventory_items(items),
    )


def _render_answer_prompt(cid: int, p: _P) -> game.schemas.GameResponse:
    remaining = p.get("remaining_seconds", 0)
    return _make(
        cid,
        (f"⏱ Осталось {remaining} сек на ответ.\nВведите ответ!"),
        keyboard=bot.keyboards.answer_prompt(),
    )


def _render_inventory_empty(cid: int, _p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        "📦 Инвентарь пуст! Зайдите в /shop, чтобы купить предметы."
        "\n\nВведите ответ!",
        keyboard=bot.keyboards.answer_prompt(),
    )


def _render_item_used(cid: int, p: _P) -> game.schemas.GameResponse:
    return _make(cid, p["text"])


def _render_item_used_group(cid: int, p: _P) -> game.schemas.GameResponse:
    emoji = p["emoji"]
    name = p["name"]
    remaining = p.get("remaining_seconds", 0)
    effect_text = p.get("effect_text", "")
    text = effect_text if effect_text else f"✨ {emoji} {name} использован!"
    text += f"\n⏱ Осталось {remaining} сек"
    return _make(
        cid,
        text,
        keyboard=bot.keyboards.answer_prompt(),
    )


def _render_lobby_cancelled(cid: int, _p: _P) -> game.schemas.GameResponse:
    return _make(
        cid,
        "😢 Игра отменена из-за неактивности в лобби.",
        keyboard=[],
    )


def _render_csv_upload_result(cid: int, p: _P) -> game.schemas.GameResponse:
    created = p["created"]
    errors = p.get("errors", [])
    lines = [f"📊 Импорт CSV завершён: {created} вопросов добавлено."]
    if errors:
        lines.append(f"\n⚠️ Ошибки ({len(errors)}):")
        lines.extend(f"  • {err}" for err in errors[:10])
        if len(errors) > 10:
            lines.append(f"  … и ещё {len(errors) - 10}")
    return _make(cid, "\n".join(lines))


def _render_my_content_topics(cid: int, p: _P) -> game.schemas.GameResponse:
    topics = p["topics_with_counts"]
    total_q = sum(count for _, count in topics)
    lines = [
        f"📚 Ваш контент: {len(topics)} тем, {total_q} вопросов\n",
        "Выберите тему для просмотра:",
    ]
    return _make(
        cid,
        "\n".join(lines),
        keyboard=bot.keyboards.my_content_topics(topics),
    )


def _render_my_content_questions(cid: int, p: _P) -> game.schemas.GameResponse:
    topic_title = p["topic_title"]
    questions = p["questions"]
    if not questions:
        return _make(
            cid,
            f"📂 Тема «{topic_title}»\n\n📭 У вас нет вопросов в этой теме.",
            keyboard=bot.keyboards.my_content_questions([], p["topic_id"]),
        )
    lines = [
        f"📂 Тема «{topic_title}» — {len(questions)} вопросов\n",
        "Нажмите на вопрос, чтобы увидеть ответ:",
    ]
    return _make(
        cid,
        "\n".join(lines),
        keyboard=bot.keyboards.my_content_questions(questions, p["topic_id"]),
    )


def _render_my_content_question_detail(
    cid: int, p: _P
) -> game.schemas.GameResponse:
    return _make(
        cid,
        (
            f"📂 Тема: {p['topic_title']}\n"
            f"💰 Стоимость: {p['question_cost']} очков\n\n"
            f"❓ {p['question_text']}\n\n"
            f"✅ Ответ: {p['question_answer']}"
        ),
        keyboard=bot.keyboards.my_content_question_back(p["topic_id"]),
    )


def _render_csv_upload_preview(cid: int, p: _P) -> game.schemas.GameResponse:
    total = p["total"]
    sample = p.get("sample", [])
    lines = [f"📋 Предпросмотр CSV ({total} строк):"]
    lines.extend(
        f"  [{row['topic']}] {row['question'][:40]}… "
        f"→ {row['answer']} ({row['cost']})"
        for row in sample
    )
    if total > len(sample):
        lines.append(f"  … и ещё {total - len(sample)}")
    return _make(cid, "\n".join(lines))


def _render_balance_info(cid: int, p: _P) -> game.schemas.GameResponse:
    balance = p["balance"]
    item_count = p.get("item_count", 0)
    return _make(
        cid,
        (f"💰 Баланс: {balance} очк.\n📦 Предметов: {item_count}"),
    )


def _render_daily_reward_claimed(cid: int, p: _P) -> game.schemas.GameResponse:
    amount = p["amount"]
    new_balance = p["new_balance"]
    return _make(
        cid,
        (
            f"🎁 Ежедневная награда получена!\n\n"
            f"💰 +{amount} очк.\n"
            f"💰 Новый баланс: {new_balance} очк."
        ),
    )


_SIMPLE_VIEWS: dict[game.constants.ViewName, str] = {
    game.constants.ViewName.NO_ACTIVE_GAME: (
        "🎮 Здесь нет активной игры. Создайте её командой /start!"
    ),
    game.constants.ViewName.NO_ACTIVE_GAME_HERE: (
        "🤷 В этом чате нет активной игры."
    ),
    game.constants.ViewName.GAME_ALREADY_RUNNING: (
        "⚠️ В этом чате уже идёт игра!"
    ),
    game.constants.ViewName.GAME_ALREADY_STARTED: (
        "⏳ Игра уже началась. Ждите следующего раунда!"
    ),
    game.constants.ViewName.GAME_IN_PROGRESS: ("🕹 Игра уже идёт!"),
    game.constants.ViewName.ONLY_HOST: (
        "🚫 Только ведущий может выполнить это действие."
    ),
    game.constants.ViewName.NEED_TWO_PLAYERS: (
        "👥 Нужно минимум 2 игрока. Позовите друзей!"
    ),
    game.constants.ViewName.NO_QUESTIONS: (
        "📭 В базе нет вопросов. Добавьте их сначала!"
    ),
    game.constants.ViewName.NOT_YOUR_TURN: (
        "🙅 Сейчас не ваш ход выбирать вопрос."
    ),
    game.constants.ViewName.DIALOG_PROMPT_TOPIC: ("📝 Введите название темы:"),
    game.constants.ViewName.DIALOG_PROMPT_QUESTION: (
        "✏️ Отправьте текст вопроса:"
    ),
    game.constants.ViewName.DIALOG_PROMPT_ANSWER: (
        "💡 Теперь отправьте правильный ответ:"
    ),
    game.constants.ViewName.DIALOG_PROMPT_COST: (
        "💰 Введите стоимость в очках (напр. 100, 200, 500):"
    ),
    game.constants.ViewName.DIALOG_CANCELLED: "❌ Отменено.",
    game.constants.ViewName.DIALOG_DONE: "✅ Готово!",
    game.constants.ViewName.DB_ERROR: (game.constants.BotMessage.DB_ERROR),
    game.constants.ViewName.UNKNOWN_COMMAND: (
        "🤔 Неизвестная команда. Напишите /help, чтобы увидеть список!"
    ),
    game.constants.ViewName.GROUP_ONLY_COMMAND: (
        "❌ Эта команда только для групп. Добавьте меня в группу, чтобы играть!"
    ),
}


def _render_simple_with_username(
    cid: int, p: _P, template: str
) -> game.schemas.GameResponse:
    return _make(cid, template.format(username=p["username"]))


_USERNAME_VIEWS: dict[game.constants.ViewName, str] = {
    game.constants.ViewName.ALREADY_IN_GAME: ("ℹ️ {username}, вы уже в игре!"),
    game.constants.ViewName.ALREADY_SPECTATING: (
        "ℹ️ {username}, вы уже смотрите игру!"
    ),
    game.constants.ViewName.NOT_IN_GAME: ("🤔 {username}, вы не в этой игре."),
}

_ALERT_VIEWS: frozenset[game.constants.ViewName] = frozenset(
    {
        game.constants.ViewName.NO_ACTIVE_GAME,
        game.constants.ViewName.NO_ACTIVE_GAME_HERE,
        game.constants.ViewName.GAME_ALREADY_RUNNING,
        game.constants.ViewName.GAME_ALREADY_STARTED,
        game.constants.ViewName.GAME_IN_PROGRESS,
        game.constants.ViewName.ONLY_HOST,
        game.constants.ViewName.NEED_TWO_PLAYERS,
        game.constants.ViewName.NO_QUESTIONS,
        game.constants.ViewName.NOT_YOUR_TURN,
        game.constants.ViewName.ALREADY_IN_GAME,
        game.constants.ViewName.ALREADY_SPECTATING,
        game.constants.ViewName.NOT_IN_GAME,
        game.constants.ViewName.PLAYER_JOINED,
        game.constants.ViewName.PLAYER_REJOINED,
        game.constants.ViewName.NOW_SPECTATING,
        game.constants.ViewName.LEFT_GAME,
        game.constants.ViewName.HOST_TRANSFERRED,
    }
)


_RENDERERS: dict[game.constants.ViewName, Renderer] = {
    game.constants.ViewName.GAME_CREATED: _render_game_created,
    game.constants.ViewName.LOBBY: _render_lobby,
    game.constants.ViewName.PLAYER_JOINED: _render_player_joined,
    game.constants.ViewName.PLAYER_REJOINED: _render_player_rejoined,
    game.constants.ViewName.NOW_SPECTATING: _render_now_spectating,
    game.constants.ViewName.LEFT_GAME: _render_left_game,
    game.constants.ViewName.HOST_TRANSFERRED: _render_host_transferred,
    game.constants.ViewName.SCOREBOARD: _render_scoreboard,
    game.constants.ViewName.BOARD: _render_board,
    game.constants.ViewName.QUESTION_ASKED: _render_question_asked,
    game.constants.ViewName.CAT_REVEALED: _render_cat_revealed,
    game.constants.ViewName.BUZZER_PRESSED: _render_buzzer_pressed,
    game.constants.ViewName.ALL_IN_ACTIVATED: _render_all_in_activated,
    game.constants.ViewName.ANSWER_CORRECT: _render_answer_correct,
    game.constants.ViewName.ANSWER_WRONG: _render_answer_wrong,
    game.constants.ViewName.BUZZER_TIMEOUT: _render_buzzer_timeout,
    game.constants.ViewName.ANSWER_TIMEOUT: _render_answer_timeout,
    game.constants.ViewName.CHOOSING_TIMEOUT: _render_choosing_timeout,
    game.constants.ViewName.GAME_ENDED_NO_PLAYERS: (
        _render_game_ended_no_players
    ),
    game.constants.ViewName.GAME_ENDED_AFK: _render_game_ended_afk,
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
    game.constants.ViewName.TOPIC_SELECT_FOR_RESTORE: (
        _render_topic_select_for_restore
    ),
    game.constants.ViewName.QUESTION_SELECT_FOR_RESTORE: (
        _render_question_select_for_restore
    ),
    game.constants.ViewName.HELP: _render_help,
    game.constants.ViewName.RULES: _render_rules,
    game.constants.ViewName.MY_GAMES: _render_my_games,
    game.constants.ViewName.PRIVATE_ONLY_COMMAND: (
        _render_private_only_command
    ),
    game.constants.ViewName.SHOP_REDIRECT: _render_shop_redirect,
    game.constants.ViewName.SHOP_MAIN: _render_shop_main,
    game.constants.ViewName.SHOP_CATEGORY: _render_shop_category,
    game.constants.ViewName.SHOP_BUY_OK: _render_shop_buy_ok,
    game.constants.ViewName.SHOP_INSUFFICIENT: _render_shop_insufficient,
    game.constants.ViewName.ANSWER_PROMPT: _render_answer_prompt,
    game.constants.ViewName.INVENTORY_LIST: _render_inventory_list,
    game.constants.ViewName.INVENTORY_EMPTY: _render_inventory_empty,
    game.constants.ViewName.ITEM_USED: _render_item_used,
    game.constants.ViewName.ITEM_USED_GROUP: _render_item_used_group,
    game.constants.ViewName.BALANCE_INFO: _render_balance_info,
    game.constants.ViewName.DAILY_REWARD_CLAIMED: _render_daily_reward_claimed,
    game.constants.ViewName.LOBBY_CANCELLED: _render_lobby_cancelled,
    game.constants.ViewName.CSV_UPLOAD_RESULT: _render_csv_upload_result,
    game.constants.ViewName.CSV_UPLOAD_PREVIEW: _render_csv_upload_preview,
    game.constants.ViewName.MY_CONTENT_TOPICS: _render_my_content_topics,
    game.constants.ViewName.MY_CONTENT_QUESTIONS: (
        _render_my_content_questions
    ),
    game.constants.ViewName.MY_CONTENT_QUESTION_DETAIL: (
        _render_my_content_question_detail
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
        result = renderer(cid, p)
    elif view == game.constants.ViewName.PLAIN:
        result = _make(cid, p["text"])
    else:
        simple_text = _SIMPLE_VIEWS.get(view)
        if simple_text is not None:
            result = _make(cid, simple_text)
        else:
            username_template = _USERNAME_VIEWS.get(view)
            if username_template is not None:
                result = _render_simple_with_username(cid, p, username_template)
            else:
                result = _make(cid, "⚠️ Произошла непредвиденная ошибка.")

    if response.edit_message_id is not None:
        result.edit_message_id = response.edit_message_id
    if view in _ALERT_VIEWS or response.is_alert:
        result.is_alert = True
    if response.lobby_game_id:
        result.lobby_game_id = response.lobby_game_id
    return result
