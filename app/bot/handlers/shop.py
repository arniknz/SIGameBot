from __future__ import annotations

import re

import bot.router
import bot.views
import game.constants
import game.services


def register(
    router: bot.router.Router,
    shop: game.services.ShopService,
) -> None:
    _register_commands(router, shop)
    _register_callbacks(router, shop)


def _register_commands(
    router: bot.router.Router,
    shop: game.services.ShopService,
) -> None:
    @router.command(game.constants.Command.SHOP, private=True)
    async def cmd_shop(chat_id: int, telegram_id: int, **_):
        result = await shop.handle_shop_main(chat_id, telegram_id)
        return bot.views.render_many(result)

    @router.command(game.constants.Command.BALANCE, private=True)
    async def cmd_balance(chat_id: int, telegram_id: int, **_):
        result = await shop.handle_balance(chat_id, telegram_id)
        return bot.views.render_many(result)


def _register_callbacks(
    router: bot.router.Router,
    shop: game.services.ShopService,
) -> None:
    @router.callback(game.constants.Callback.SHOP)
    async def cb_shop(
        chat_id: int, telegram_id: int, bot_username: str = "", **_
    ):
        is_private = chat_id == telegram_id
        if is_private:
            result = await shop.handle_shop_main(chat_id, telegram_id)
        else:
            result = await shop.handle_shop_redirect(chat_id, bot_username)
        return bot.views.render_many(result)

    @router.callback(game.constants.Callback.INVENTORY)
    async def cb_inventory(
        chat_id: int,
        telegram_id: int,
        username: str,
        message_id: int = 0,
        **_,
    ):
        result = await shop.handle_inventory_request(
            chat_id, telegram_id, username, message_id=message_id
        )
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.SHOP_CATEGORY}:(.+)$"
    )
    async def cb_shop_category(
        match: re.Match[str], chat_id: int, telegram_id: int, **_
    ):
        category_str = match.group(1)
        result = await shop.handle_shop_category(
            chat_id, telegram_id, category_str
        )
        return bot.views.render_many(result)

    @router.callback_pattern(
        rf"^{game.constants.CallbackPrefix.SHOP_BUY}:(.+)$"
    )
    async def cb_shop_buy(
        match: re.Match[str], chat_id: int, telegram_id: int, **_
    ):
        item_id_str = match.group(1)
        result = await shop.handle_buy(chat_id, telegram_id, item_id_str)
        return bot.views.render_many(result)

    @router.callback_pattern(rf"^{game.constants.CallbackPrefix.INV_USE}:(.+)$")
    async def cb_inv_use(
        match: re.Match[str],
        chat_id: int,
        telegram_id: int,
        message_id: int = 0,
        **_,
    ):
        item_id_str = match.group(1)
        result = await shop.handle_use_item(
            chat_id, telegram_id, item_id_str, message_id=message_id
        )
        return bot.views.render_many(result)
