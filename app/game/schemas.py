import dataclasses
import typing

import game.constants


@dataclasses.dataclass
class GameResponse:
    chat_id: int
    text: str
    keyboard: list[list[dict[str, str]]] | None = None
    edit_message_id: int | None = None
    is_alert: bool = False
    lobby_game_id: str | None = None


@dataclasses.dataclass
class ServiceResponse:
    chat_id: int
    view: game.constants.ViewName
    payload: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    edit_message_id: int | None = None
    is_alert: bool = False
    lobby_game_id: str | None = None


@dataclasses.dataclass
class DialogState:
    step: game.constants.DialogStep
    game_chat_id: int = 0
    topic_name: str = ""
    topic_id: str = ""
    question_text: str = ""
    question_answer: str = ""
    question_cost: int = 0
