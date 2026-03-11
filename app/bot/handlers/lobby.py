from __future__ import annotations

import bot.router
import bot.views
import game.constants
import game.services


def register(
    router: bot.router.Router, lobby: game.services.LobbyService
) -> None:

    @router.command(game.constants.Command.START)
    async def cmd_start(chat_id: int, telegram_id: int, username: str, **_):
        result = await lobby.handle_start(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.JOIN)
    async def cb_join(chat_id: int, telegram_id: int, username: str, **_):
        result = await lobby.handle_join(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.SPECTATE)
    async def cb_spectate(chat_id: int, telegram_id: int, username: str, **_):
        result = await lobby.handle_spectate(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.LEAVE)
    async def cb_leave(chat_id: int, telegram_id: int, username: str, **_):
        result = await lobby.handle_leave(chat_id, telegram_id, username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.STOP)
    async def cb_stop(chat_id: int, telegram_id: int, **_):
        result = await lobby.handle_stop(chat_id, telegram_id)
        return bot.views.render_many(result)
