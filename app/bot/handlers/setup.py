from __future__ import annotations

import bot.dialog
import bot.handlers.common
import bot.handlers.content
import bot.handlers.game
import bot.handlers.lobby
import bot.router
import game.services


def create_router(
    lobby: game.services.LobbyService,
    gameplay: game.services.GameplayService,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
) -> bot.router.Router:
    router = bot.router.Router()
    bot.handlers.lobby.register(router, lobby)
    bot.handlers.game.register(router, gameplay)
    bot.handlers.content.register(router, content, dialog)
    bot.handlers.common.register(router, content)
    return router
