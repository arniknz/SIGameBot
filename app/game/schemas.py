from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class GameResponse:
    chat_id: int
    text: str
    keyboard: list[list[dict]] | None = None


@dataclasses.dataclass
class DialogState:
    step: str
    game_chat_id: int = 0
    topic_name: str = ""
    topic_id: str = ""
    question_text: str = ""
    question_answer: str = ""
    question_cost: int = 0
