from __future__ import annotations

import logging

import game.schemas

logger = logging.getLogger(__name__)

STEP_IDLE = "idle"
STEP_AWAIT_TOPIC_NAME = "await_topic_name"
STEP_AWAIT_QUESTION_TEXT = "await_question_text"
STEP_AWAIT_QUESTION_ANSWER = "await_question_answer"
STEP_AWAIT_QUESTION_COST = "await_question_cost"


class DialogManager:
    def __init__(self) -> None:
        self._states: dict[int, game.schemas.DialogState] = {}

    def get(self, telegram_id: int) -> game.schemas.DialogState | None:
        return self._states.get(telegram_id)

    def start_add_topic(self, telegram_id: int, game_chat_id: int) -> None:
        self._states[telegram_id] = game.schemas.DialogState(
            step=STEP_AWAIT_TOPIC_NAME,
            game_chat_id=game_chat_id,
        )
        logger.debug(
            "User %d started add_topic dialog for chat %d",
            telegram_id,
            game_chat_id,
        )

    def start_add_question(
        self, telegram_id: int, game_chat_id: int, topic_id: str
    ) -> None:
        self._states[telegram_id] = game.schemas.DialogState(
            step=STEP_AWAIT_QUESTION_TEXT,
            game_chat_id=game_chat_id,
            topic_id=topic_id,
        )
        logger.debug(
            "User %d started add_question dialog for topic %s",
            telegram_id,
            topic_id,
        )

    def advance(self, telegram_id: int, step: str) -> None:
        state = self._states.get(telegram_id)
        if state:
            state.step = step

    def clear(self, telegram_id: int) -> None:
        self._states.pop(telegram_id, None)

    def has_active(self, telegram_id: int) -> bool:
        state = self._states.get(telegram_id)
        return state is not None and state.step != STEP_IDLE
