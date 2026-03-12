from __future__ import annotations

import re

import bot.router
import bot.views
import game.constants
import game.services


def register(
    router: bot.router.Router, gameplay: game.services.GameplayService
) -> None:

    @router.command(game.constants.Command.START_GAME)
    async def cmd_start_game(chat_id: int, telegram_id: int, **_):
        result = await gameplay.handle_start_game(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.SCORE)
    async def cmd_score(chat_id: int, **_):
        result = await gameplay.handle_score(chat_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.BUZZER)
    async def cb_buzzer(chat_id: int, telegram_id: int, username: str, **_):
        result = await gameplay.handle_buzzer(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.CAT_IN_BAG)
    async def cb_cat_in_bag(chat_id: int, telegram_id: int, **_):
        result = await gameplay.handle_cat_in_bag(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.ALL_IN)
    async def cb_all_in(chat_id: int, telegram_id: int, username: str, **_):
        result = await gameplay.handle_all_in(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.QUESTION}:(.+)$"
    )
    async def cb_question(
        match: re.Match[str], chat_id: int, telegram_id: int, **_
    ):
        question_in_game_id = match.group(1)
        result = await gameplay.handle_question_selected(
            chat_id, telegram_id, question_in_game_id
        )
        return bot.views.render_many(result)
