from __future__ import annotations

import enum


class GameStatus(enum.StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


class ParticipantRole(enum.StrEnum):
    PLAYER = "player"
    SPECTATOR = "spectator"


class GamePhase(enum.StrEnum):
    LOBBY = "lobby"
    CHOOSING_QUESTION = "choosing_question"
    WAITING_BUZZER = "waiting_buzzer"
    WAITING_ANSWER = "waiting_answer"
    FINISHED = "finished"


class QuestionInGameStatus(enum.StrEnum):
    PENDING = "pending"
    ASKED = "asked"
    ANSWERED = "answered"


class BotMessage(enum.StrEnum):
    DB_ERROR = "⚠️ Bot is temporarily unavailable. Please try again later."


class Command(enum.StrEnum):
    START = "start"
    START_GAME = "start_game"
    SCORE = "score"
    MY_GAMES = "my_games"
    ADD_TOPIC = "add_topic"
    ADD_QUESTION = "add_question"
    DELETE_TOPIC = "delete_topic"
    DELETE_QUESTION = "delete_question"
    HELP = "help"
    RULES = "rules"
    DONE = "done"
    CANCEL = "cancel"


class Callback(enum.StrEnum):
    JOIN = "join"
    SPECTATE = "spectate"
    LEAVE = "leave"
    STOP = "stop"
    BUZZER = "buzzer"
    HELP = "help"
    RULES = "rules"


class CallbackPrefix(enum.StrEnum):
    QUESTION = "q"
    DELETE_TOPIC = "del_topic"
    DELETE_QUESTION_TOPIC = "delq_topic"
    DELETE_QUESTION_CONFIRM = "delq_confirm"
    ADD_QUESTION_TOPIC = "addq_topic"


class DialogStep(enum.StrEnum):
    IDLE = "idle"
    AWAIT_TOPIC_NAME = "await_topic_name"
    AWAIT_QUESTION_TEXT = "await_question_text"
    AWAIT_QUESTION_ANSWER = "await_question_answer"
    AWAIT_QUESTION_COST = "await_question_cost"
