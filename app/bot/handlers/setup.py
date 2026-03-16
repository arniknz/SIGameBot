from __future__ import annotations

import bot.dialog
import bot.handlers.common
import bot.handlers.content
import bot.handlers.game
import bot.handlers.lobby
import bot.handlers.shop
import bot.router
import game.services


def create_router(
    lobby: game.services.LobbyService,
    gameplay: game.services.GameplayService,
    content: game.services.ContentService,
    dialog: bot.dialog.DialogManager,
    shop: game.services.ShopService,
) -> bot.router.Router:
    router = bot.router.Router()
    bot.handlers.lobby.register(router, lobby, gameplay)
    bot.handlers.game.register(router, gameplay)
    bot.handlers.content.register(router, content, dialog, shop)
    bot.handlers.common.register(router, content)
    bot.handlers.shop.register(router, shop)
    return router
