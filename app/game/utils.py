from __future__ import annotations

import game.constants
import game.schemas


def service_result(
    chat_id: int,
    view: game.constants.ViewName,
    *,
    is_alert: bool = False,
    edit_message_id: int | None = None,
    lobby_game_id: str | None = None,
    **payload: object,
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
        is_alert=is_alert,
        edit_message_id=edit_message_id,
        lobby_game_id=lobby_game_id,
    )
