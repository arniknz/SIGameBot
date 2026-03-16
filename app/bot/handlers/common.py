from __future__ import annotations

import bot.router
import game.constants
import game.schemas
import game.services


def _dm_redirect(
    chat_id: int,
    label: str,
    bot_username: str,
    deeplink: str,
) -> list[game.schemas.GameResponse]:
    text = f"{label} \u2014 смотрите в личке со мной."
    kb: list[list[dict[str, str]]] | None = None
    if bot_username:
        kb = [
            [
                {
                    "text": "\U0001f4e9 Открыть личку",
                    "url": f"https://t.me/{bot_username}?start={deeplink}",
                }
            ]
        ]
    return [game.schemas.GameResponse(chat_id=chat_id, text=text, keyboard=kb)]


def register(
    router: bot.router.Router, content: game.services.ContentService
) -> None:

    @router.command(game.constants.Command.HELP)
    def cmd_help_group(chat_id: int, bot_username: str = "", **_):
        return _dm_redirect(chat_id, "\u2753 Справка", bot_username, "help")

    @router.command(game.constants.Command.RULES)
    def cmd_rules_group(chat_id: int, bot_username: str = "", **_):
        return _dm_redirect(
            chat_id, "\U0001f4d6 Правила", bot_username, "rules"
        )

    @router.callback(game.constants.Callback.HELP)
    def cb_help(chat_id: int, **_):
        return [
            game.schemas.GameResponse(
                chat_id=chat_id,
                text="\u2753 Используйте /help в личке со мной!",
                is_alert=True,
            )
        ]

    @router.callback(game.constants.Callback.RULES)
    def cb_rules(chat_id: int, **_):
        return [
            game.schemas.GameResponse(
                chat_id=chat_id,
                text="\U0001f4d6 Используйте /rules в личке со мной!",
                is_alert=True,
            )
        ]
