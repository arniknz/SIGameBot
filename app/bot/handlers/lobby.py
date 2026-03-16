from __future__ import annotations

import bot.router
import bot.views
import game.constants
import game.schemas
import game.services

_NOTIFICATION_VIEWS: frozenset[game.constants.ViewName] = frozenset(
    {
        game.constants.ViewName.PLAYER_JOINED,
        game.constants.ViewName.PLAYER_REJOINED,
        game.constants.ViewName.NOW_SPECTATING,
        game.constants.ViewName.LEFT_GAME,
        game.constants.ViewName.HOST_TRANSFERRED,
    }
)


def _with_alert(
    result: list[game.schemas.ServiceResponse],
    chat_id: int,
) -> list[game.schemas.GameResponse]:
    custom_alert: game.schemas.GameResponse | None = None
    for sr in result:
        alert = sr.payload.get("alert_text")
        if alert:
            custom_alert = game.schemas.GameResponse(
                chat_id=chat_id,
                text=str(alert),
                is_alert=True,
            )
            break

    responses = bot.views.render_many(result)
    if custom_alert:
        responses.insert(0, custom_alert)
    return responses


def _render_no_notifications(
    result: list[game.schemas.ServiceResponse],
) -> list[game.schemas.GameResponse]:
    filtered = [sr for sr in result if sr.view not in _NOTIFICATION_VIEWS]
    return bot.views.render_many(filtered)


def register(
    router: bot.router.Router,
    lobby: game.services.LobbyService,
    gameplay: game.services.GameplayService,
) -> None:

    @router.command(game.constants.Command.START)
    async def cmd_start(
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_start(
            chat_id, telegram_id, username, bot_username
        )
        return bot.views.render_many(result)

    @router.command(game.constants.Command.JOIN)
    async def cmd_join(
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_join(
            chat_id, telegram_id, username, bot_username
        )
        return _render_no_notifications(result)

    @router.callback(game.constants.Callback.JOIN)
    async def cb_join(
        chat_id: int,
        telegram_id: int,
        username: str,
        message_id: int = 0,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_join(
            chat_id,
            telegram_id,
            username,
            bot_username,
            lobby_message_id=message_id,
        )
        return _with_alert(result, chat_id)

    @router.command(game.constants.Command.SPECTATE)
    async def cmd_spectate(
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_spectate(
            chat_id, telegram_id, username, bot_username
        )
        return _render_no_notifications(result)

    @router.callback(game.constants.Callback.SPECTATE)
    async def cb_spectate(
        chat_id: int,
        telegram_id: int,
        username: str,
        message_id: int = 0,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_spectate(
            chat_id,
            telegram_id,
            username,
            bot_username,
            lobby_message_id=message_id,
        )
        return _with_alert(result, chat_id)

    @router.command(game.constants.Command.LEAVE)
    async def cmd_leave(
        chat_id: int,
        telegram_id: int,
        username: str,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_leave(
            chat_id, telegram_id, username, bot_username
        )
        return _render_no_notifications(result)

    @router.callback(game.constants.Callback.LEAVE)
    async def cb_leave(
        chat_id: int,
        telegram_id: int,
        username: str,
        message_id: int = 0,
        bot_username: str = "",
        **_,
    ):
        result = await lobby.handle_leave(
            chat_id,
            telegram_id,
            username,
            bot_username,
            lobby_message_id=message_id,
        )
        return _with_alert(result, chat_id)

    @router.command(game.constants.Command.STOP)
    async def cmd_stop(chat_id: int, telegram_id: int, **_):
        result = await lobby.handle_stop(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.STOP)
    async def cb_stop(chat_id: int, telegram_id: int, **_):
        result = await lobby.handle_stop(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.START_GAME)
    async def cb_start_game(chat_id: int, telegram_id: int, **_):
        result = await gameplay.handle_start_game(chat_id, telegram_id)
        return bot.views.render_many(result)
