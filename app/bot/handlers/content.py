from __future__ import annotations

import re

import bot.dialog
import bot.router
import bot.views
import game.constants
import game.schemas
import game.services


def register(
    router: bot.router.Router,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
) -> None:
    _register_commands(router, content, dialog)
    _register_callbacks(router, content, dialog)


def _register_commands(
    router: bot.router.Router,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
) -> None:
    @router.command(game.constants.Command.START, private=True)
    async def cmd_private_start(chat_id: int, **_):
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.MY_GAMES, private=True)
    async def cmd_my_games(chat_id: int, telegram_id: int, **_):
        result = await content.handle_my_games(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.ADD_QUESTION, private=True)
    async def cmd_add_question(chat_id: int, **_):
        result = await content.topic_keyboard_for_add(chat_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.DELETE_TOPIC, private=True)
    async def cmd_delete_topic(chat_id: int, telegram_id: int, **_):
        result = await content.handle_delete_topic(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.DELETE_QUESTION, private=True)
    async def cmd_delete_question(chat_id: int, telegram_id: int, **_):
        result = await content.handle_delete_question(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.HELP, private=True)
    async def cmd_help(chat_id: int, **_):
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.RULES, private=True)
    async def cmd_rules(chat_id: int, **_):
        result = await content.handle_rules(chat_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.ADD_TOPIC, private=True)
    def cmd_add_topic(telegram_id: int, chat_id: int, **_):
        dialog.start_add_topic(telegram_id, game_chat_id=0)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_PROMPT_TOPIC,
                )
            ]
        )

    @router.command(game.constants.Command.CANCEL, private=True)
    @router.command(game.constants.Command.DONE, private=True)
    def cmd_cancel_or_done(telegram_id: int, chat_id: int, **_):
        dialog.clear(telegram_id)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_DONE,
                )
            ]
        )


def _register_callbacks(
    router: bot.router.Router,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
) -> None:
    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_TOPIC}:(.+)$"
    )
    async def cb_del_topic(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id,
                        game.constants.ViewName.DIALOG_CANCELLED,
                    )
                ]
            )
        result = await content.confirm_delete_topic(chat_id, telegram_id, value)
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_QUESTION_TOPIC}:(.+)$"
    )
    async def cb_delq_topic(match: re.Match[str], chat_id: int, **_):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id,
                        game.constants.ViewName.DIALOG_CANCELLED,
                    )
                ]
            )
        result = await content.list_questions_for_delete(chat_id, value)
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_QUESTION_CONFIRM}:(.+)$"
    )
    async def cb_delq_confirm(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id,
                        game.constants.ViewName.DIALOG_CANCELLED,
                    )
                ]
            )
        result = await content.confirm_delete_question(
            chat_id, telegram_id, value
        )
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.ADD_QUESTION_TOPIC}:(.+)$"
    )
    def cb_addq_topic(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id,
                        game.constants.ViewName.DIALOG_CANCELLED,
                    )
                ]
            )
        dialog.start_add_question(telegram_id, game_chat_id=0, topic_id=value)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_PROMPT_QUESTION,
                )
            ]
        )
