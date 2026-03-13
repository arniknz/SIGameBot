from __future__ import annotations

import dataclasses
import typing

from game.constants import DialogStep, ViewName


@dataclasses.dataclass
class GameResponse:
    chat_id: int
    text: str
    keyboard: list[list[dict[str, str]]] | None = None
    edit_message_id: int | None = None


@dataclasses.dataclass
class ServiceResponse:
    chat_id: int
    view: ViewName
    payload: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    edit_message_id: int | None = None


@dataclasses.dataclass
class DialogState:
    step: DialogStep
    game_chat_id: int = 0
    topic_name: str = ""
    topic_id: str = ""
    question_text: str = ""
    question_answer: str = ""
    question_cost: int = 0
