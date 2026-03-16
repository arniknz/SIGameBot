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
    shop: game.services.ShopService | None = None,
) -> None:
    _register_commands(router, content, dialog, shop)
    _register_callbacks(router, content, dialog)


def _make_private_start(content: game.services.ContentService, shop):
    async def handler(chat_id: int, telegram_id: int, args: str = "", **_):
        if args == "shop" and shop is not None:
            result = await shop.handle_shop_main(chat_id, telegram_id)
            return bot.views.render_many(result)
        if args == "rules":
            result = await content.handle_rules(chat_id)
            return bot.views.render_many(result)
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    return handler


def _make_my_games(content: game.services.ContentService):
    async def handler(chat_id: int, telegram_id: int, **_):
        result = await content.handle_my_games(chat_id, telegram_id)
        return bot.views.render_many(result)

    return handler


def _make_add_question(content: game.services.ContentService):
    async def handler(chat_id: int, **_):
        result = await content.topic_keyboard_for_add(chat_id)
        return bot.views.render_many(result)

    return handler


def _make_delete_topic(content: game.services.ContentService):
    async def handler(chat_id: int, telegram_id: int, **_):
        result = await content.handle_delete_topic(chat_id, telegram_id)
        return bot.views.render_many(result)

    return handler


def _make_delete_question(content: game.services.ContentService):
    async def handler(chat_id: int, telegram_id: int, **_):
        result = await content.handle_delete_question(chat_id, telegram_id)
        return bot.views.render_many(result)

    return handler


def _make_restore_topic(content: game.services.ContentService):
    async def handler(chat_id: int, telegram_id: int, **_):
        result = await content.handle_restore_topic(chat_id, telegram_id)
        return bot.views.render_many(result)

    return handler


def _make_restore_question(content: game.services.ContentService):
    async def handler(chat_id: int, telegram_id: int, **_):
        result = await content.handle_restore_question(chat_id, telegram_id)
        return bot.views.render_many(result)

    return handler


def _make_help(content: game.services.ContentService):
    async def handler(chat_id: int, **_):
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    return handler


def _make_rules(content: game.services.ContentService):
    async def handler(chat_id: int, **_):
        result = await content.handle_rules(chat_id)
        return bot.views.render_many(result)

    return handler


def _make_add_topic(dialog: bot.dialog.DialogManager):
    def handler(telegram_id: int, chat_id: int, **_):
        dialog.start_add_topic(telegram_id, game_chat_id=0)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_PROMPT_TOPIC,
                )
            ]
        )

    return handler


def _make_cancel_or_done(dialog: bot.dialog.DialogManager):
    def handler(telegram_id: int, chat_id: int, **_):
        dialog.clear(telegram_id)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_DONE,
                )
            ]
        )

    return handler


def _register_commands(
    router: bot.router.Router,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
    shop: game.services.ShopService | None = None,
) -> None:
    router.command(game.constants.Command.START, private=True)(
        _make_private_start(content, shop)
    )
    router.command(game.constants.Command.MY_GAMES, private=True)(
        _make_my_games(content)
    )
    router.command(game.constants.Command.ADD_QUESTION, private=True)(
        _make_add_question(content)
    )
    router.command(game.constants.Command.DELETE_TOPIC, private=True)(
        _make_delete_topic(content)
    )
    router.command(game.constants.Command.DELETE_QUESTION, private=True)(
        _make_delete_question(content)
    )
    router.command(game.constants.Command.RESTORE_TOPIC, private=True)(
        _make_restore_topic(content)
    )
    router.command(game.constants.Command.RESTORE_QUESTION, private=True)(
        _make_restore_question(content)
    )
    router.command(game.constants.Command.HELP, private=True)(
        _make_help(content)
    )
    router.command(game.constants.Command.RULES, private=True)(
        _make_rules(content)
    )
    router.command(game.constants.Command.ADD_TOPIC, private=True)(
        _make_add_topic(dialog)
    )
    router.command(game.constants.Command.CANCEL, private=True)(
        _make_cancel_or_done(dialog)
    )
    router.command(game.constants.Command.DONE, private=True)(
        _make_cancel_or_done(dialog)
    )


def _dialog_cancelled(chat_id: int):
    return bot.views.render_many(
        [
            game.schemas.ServiceResponse(
                chat_id,
                game.constants.ViewName.DIALOG_CANCELLED,
            )
        ]
    )


def _make_cb_del_topic(content: game.services.ContentService):
    async def handler(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        result = await content.confirm_delete_topic(chat_id, telegram_id, value)
        return bot.views.render_many(result)

    return handler


def _make_cb_delq_topic(content: game.services.ContentService):
    async def handler(match: re.Match[str], chat_id: int, **_):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        result = await content.list_questions_for_delete(chat_id, value)
        return bot.views.render_many(result)

    return handler


def _make_cb_delq_confirm(content: game.services.ContentService):
    async def handler(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        result = await content.confirm_delete_question(
            chat_id, telegram_id, value
        )
        return bot.views.render_many(result)

    return handler


def _make_cb_restore_topic(content: game.services.ContentService):
    async def handler(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        result = await content.confirm_restore_topic(
            chat_id, telegram_id, value
        )
        return bot.views.render_many(result)

    return handler


def _make_cb_restore_question(content: game.services.ContentService):
    async def handler(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        result = await content.confirm_restore_question(
            chat_id, telegram_id, value
        )
        return bot.views.render_many(result)

    return handler


def _make_cb_addq_topic(dialog: bot.dialog.DialogManager):
    def handler(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        **_,
    ):
        value = match.group(1)
        if value == game.constants.Callback.CANCEL:
            return _dialog_cancelled(chat_id)
        dialog.start_add_question(telegram_id, game_chat_id=0, topic_id=value)
        return bot.views.render_many(
            [
                game.schemas.ServiceResponse(
                    chat_id,
                    game.constants.ViewName.DIALOG_PROMPT_QUESTION,
                )
            ]
        )

    return handler


def _register_callbacks(
    router: bot.router.Router,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
) -> None:
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_TOPIC}:(.+)$"
    )(_make_cb_del_topic(content))
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_QUESTION_TOPIC}:(.+)$"
    )(_make_cb_delq_topic(content))
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.DELETE_QUESTION_CONFIRM}:(.+)$"
    )(_make_cb_delq_confirm(content))
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.RESTORE_TOPIC}:(.+)$"
    )(_make_cb_restore_topic(content))
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.RESTORE_QUESTION}:(.+)$"
    )(_make_cb_restore_question(content))
    router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.ADD_QUESTION_TOPIC}:(.+)$"
    )(_make_cb_addq_topic(dialog))
