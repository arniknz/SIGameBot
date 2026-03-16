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


class ShopCategory(enum.StrEnum):
    WEAPONS = "weapons"
    SCROLLS = "scrolls"
    ILLUSIONS = "illusions"
    TITLES = "titles"


class ItemEffect(enum.StrEnum):
    DOUBLE_POINTS = "double_points"
    NO_PENALTY = "no_penalty"
    EXTRA_TIME = "extra_time"
    REVEAL_HINT = "reveal_hint"
    REVEAL_ANSWER = "reveal_answer"
    AUTO_BUZZER = "auto_buzzer"
    PASS_ON_WRONG = "pass_on_wrong"
    FORCE_CORRECT = "force_correct"
    REPLACE_QUESTION = "replace_question"
    TRANSFER_PENALTY = "transfer_penalty"
    RESURRECT_QUESTION = "resurrect_question"
    OPEN_ANY = "open_any"
    BONUS_POINTS = "bonus_points"
    HIDE_SCORE = "hide_score"
    STEAL_POINTS = "steal_points"
    BECOME_CHOOSER = "become_chooser"


IMMEDIATE_EFFECTS: frozenset[ItemEffect] = frozenset(
    {
        ItemEffect.EXTRA_TIME,
        ItemEffect.REVEAL_HINT,
        ItemEffect.REVEAL_ANSWER,
        ItemEffect.REPLACE_QUESTION,
        ItemEffect.RESURRECT_QUESTION,
        ItemEffect.OPEN_ANY,
        ItemEffect.BONUS_POINTS,
        ItemEffect.STEAL_POINTS,
        ItemEffect.HIDE_SCORE,
    }
)

DEFERRED_EFFECTS: frozenset[ItemEffect] = frozenset(
    {
        ItemEffect.DOUBLE_POINTS,
        ItemEffect.NO_PENALTY,
        ItemEffect.PASS_ON_WRONG,
        ItemEffect.FORCE_CORRECT,
        ItemEffect.TRANSFER_PENALTY,
        ItemEffect.BECOME_CHOOSER,
        ItemEffect.AUTO_BUZZER,
    }
)

DAILY_REWARD_AMOUNT: int = 100


class BotMessage(enum.StrEnum):
    DB_ERROR = "⚠️ Упс! У бота временный сбой. Попробуйте позже!"


class Command(enum.StrEnum):
    START = "start"
    JOIN = "join"
    LEAVE = "leave"
    SPECTATE = "spectate"
    START_GAME = "start_game"
    STOP = "stop"
    SCORE = "score"
    MY_GAMES = "my_games"
    ADD_TOPIC = "add_topic"
    ADD_QUESTION = "add_question"
    DELETE_TOPIC = "delete_topic"
    DELETE_QUESTION = "delete_question"
    RESTORE_TOPIC = "restore_topic"
    RESTORE_QUESTION = "restore_question"
    SHOP = "shop"
    BALANCE = "balance"
    HELP = "help"
    RULES = "rules"
    DONE = "done"
    CANCEL = "cancel"


class Callback(enum.StrEnum):
    JOIN = "join"
    SPECTATE = "spectate"
    LEAVE = "leave"
    STOP = "stop"
    START_GAME = "start_game"
    BUZZER = "buzzer"
    CAT_IN_BAG = "cat_in_bag"
    ALL_IN = "all_in"
    HELP = "help"
    RULES = "rules"
    CANCEL = "cancel"
    SHOP = "shop"
    INVENTORY = "inventory"


class CallbackPrefix(enum.StrEnum):
    QUESTION = "q"
    DELETE_TOPIC = "del_topic"
    DELETE_QUESTION_TOPIC = "delq_topic"
    DELETE_QUESTION_CONFIRM = "delq_confirm"
    ADD_QUESTION_TOPIC = "addq_topic"
    RESTORE_TOPIC = "restore_topic"
    RESTORE_QUESTION = "restore_question"
    SHOP_CATEGORY = "shop_cat"
    SHOP_BUY = "buy"
    INV_USE = "inv_use"


class DialogStep(enum.StrEnum):
    IDLE = "idle"
    AWAIT_TOPIC_NAME = "await_topic_name"
    AWAIT_QUESTION_TEXT = "await_question_text"
    AWAIT_QUESTION_ANSWER = "await_question_answer"
    AWAIT_QUESTION_COST = "await_question_cost"


class ViewName(enum.StrEnum):
    GAME_CREATED = "game_created"
    PLAYER_JOINED = "player_joined"
    PLAYER_REJOINED = "player_rejoined"
    NOW_SPECTATING = "now_spectating"
    LEFT_GAME = "left_game"
    HOST_TRANSFERRED = "host_transferred"
    SCOREBOARD = "scoreboard"
    BOARD = "board"
    QUESTION_ASKED = "question_asked"
    BUZZER_PRESSED = "buzzer_pressed"
    ANSWER_CORRECT = "answer_correct"
    ANSWER_WRONG = "answer_wrong"
    BUZZER_TIMEOUT = "buzzer_timeout"
    ANSWER_TIMEOUT = "answer_timeout"
    CHOOSING_TIMEOUT = "choosing_timeout"
    TOPIC_SELECT_FOR_ADD = "topic_select_for_add"
    TOPIC_SELECT_FOR_DELETE = "topic_select_for_delete"
    TOPIC_SELECT_FOR_DELETE_QUESTION = "topic_select_for_delete_question"
    QUESTION_SELECT_FOR_DELETE = "question_select_for_delete"
    TOPIC_SELECT_FOR_RESTORE = "topic_select_for_restore"
    QUESTION_SELECT_FOR_RESTORE = "question_select_for_restore"
    HELP = "help"
    RULES = "rules"
    PLAIN = "plain"
    NO_ACTIVE_GAME = "no_active_game"
    NO_ACTIVE_GAME_HERE = "no_active_game_here"
    GAME_ALREADY_RUNNING = "game_already_running"
    GAME_ALREADY_STARTED = "game_already_started"
    GAME_IN_PROGRESS = "game_in_progress"
    ONLY_HOST = "only_host"
    NEED_TWO_PLAYERS = "need_two_players"
    NO_QUESTIONS = "no_questions"
    NOT_YOUR_TURN = "not_your_turn"
    ALREADY_IN_GAME = "already_in_game"
    ALREADY_SPECTATING = "already_spectating"
    NOT_IN_GAME = "not_in_game"
    DIALOG_PROMPT_TOPIC = "dialog_prompt_topic"
    DIALOG_PROMPT_QUESTION = "dialog_prompt_question"
    DIALOG_PROMPT_ANSWER = "dialog_prompt_answer"
    DIALOG_PROMPT_COST = "dialog_prompt_cost"
    DIALOG_CANCELLED = "dialog_cancelled"
    DIALOG_DONE = "dialog_done"
    DB_ERROR = "db_error"
    GAME_ENDED_NO_PLAYERS = "game_ended_no_players"
    UNKNOWN_COMMAND = "unknown_command"
    GROUP_ONLY_COMMAND = "group_only_command"
    PRIVATE_ONLY_COMMAND = "private_only_command"
    MY_GAMES = "my_games"
    SHOP_REDIRECT = "shop_redirect"
    SHOP_MAIN = "shop_main"
    SHOP_CATEGORY = "shop_category"
    SHOP_BUY_OK = "shop_buy_ok"
    SHOP_INSUFFICIENT = "shop_insufficient"
    INVENTORY_LIST = "inventory_list"
    INVENTORY_EMPTY = "inventory_empty"
    ITEM_USED = "item_used"
    ITEM_USED_GROUP = "item_used_group"
    BALANCE_INFO = "balance_info"
    DAILY_REWARD_CLAIMED = "daily_reward_claimed"
    CAT_REVEALED = "cat_revealed"
    ALL_IN_ACTIVATED = "all_in_activated"
    GAME_ENDED_AFK = "game_ended_afk"
    LOBBY = "lobby"
