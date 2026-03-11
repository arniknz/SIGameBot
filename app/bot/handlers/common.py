from __future__ import annotations

import bot.router
import bot.views
import game.constants
import game.services


def register(
    router: bot.router.Router, content: game.services.ContentService
) -> None:

    @router.command(game.constants.Command.HELP)
    async def cmd_help_group(chat_id: int, **_):
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.RULES)
    async def cmd_rules_group(chat_id: int, **_):
        result = await content.handle_rules(chat_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.HELP)
    async def cb_help(chat_id: int, **_):
        result = await content.handle_help(chat_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.RULES)
    async def cb_rules(chat_id: int, **_):
        result = await content.handle_rules(chat_id)
        return bot.views.render_many(result)
