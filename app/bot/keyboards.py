from __future__ import annotations

import uuid

import game.constants
import game.models
import sqlalchemy


def lobby() -> list[list[dict[str, str]]]:
    return [
        [
            {
                "text": "🎮 Join",
                "callback_data": game.constants.Callback.JOIN,
            },
            {
                "text": "👀 Spectate",
                "callback_data": game.constants.Callback.SPECTATE,
            },
        ],
        [
            {
                "text": "📖 Rules",
                "callback_data": game.constants.Callback.RULES,
            },
            {
                "text": "❓ Help",
                "callback_data": game.constants.Callback.HELP,
            },
        ],
    ]


def buzzer() -> list[list[dict[str, str]]]:
    return [
        [
            {
                "text": "🔔 Buzzer",
                "callback_data": game.constants.Callback.BUZZER,
            }
        ]
    ]


def score() -> list[list[dict[str, str]]]:
    return [
        [
            {
                "text": "🚪 Leave",
                "callback_data": game.constants.Callback.LEAVE,
            },
            {
                "text": "⏹ Stop",
                "callback_data": game.constants.Callback.STOP,
            },
        ]
    ]


def board(
    rows: list[sqlalchemy.Row[tuple[uuid.UUID, str, int, str, str]]],
) -> list[list[dict[str, str]]]:
    by_topic: dict[str, list[tuple[uuid.UUID, int]]] = {}
    for qig_id, topic, cost, _text, _answer in rows:
        by_topic.setdefault(topic, []).append((qig_id, cost))
    kb: list[list[dict[str, str]]] = []
    for topic, items in by_topic.items():
        row = []
        for qig_id, cost in sorted(items, key=lambda x: x[1]):
            row.append(
                {
                    "text": f"{topic} {cost}",
                    "callback_data": (
                        f"{game.constants.CallbackPrefix.QUESTION}:{qig_id}"
                    ),
                }
            )
        kb.append(row)
    return kb


def board_text(
    rows: list[sqlalchemy.Row[tuple[uuid.UUID, str, int, str, str]]],
) -> str:
    by_topic: dict[str, list[int]] = {}
    for _qig_id, topic, cost, _text, _answer in rows:
        by_topic.setdefault(topic, []).append(cost)
    lines: list[str] = []
    for topic, costs in by_topic.items():
        lines.append(f"{topic}: {' | '.join(str(c) for c in sorted(costs))}")
    return "\n".join(lines) if lines else "No questions remaining."


def topic_select_for_add(
    topics: list[game.models.TopicModel],
) -> list[list[dict[str, str]]]:
    kb: list[list[dict[str, str]]] = [
        [
            {
                "text": t.title,
                "callback_data": (
                    f"{game.constants.CallbackPrefix.ADD_QUESTION_TOPIC}:{t.id}"
                ),
            }
        ]
        for t in topics
    ]
    kb.append(
        [
            {
                "text": "❌ Cancel",
                "callback_data": (
                    f"{game.constants.CallbackPrefix.ADD_QUESTION_TOPIC}:{game.constants.Callback.CANCEL}"
                ),
            }
        ]
    )
    return kb


def topic_select_for_delete(
    topics_with_counts: list[
        sqlalchemy.Row[tuple[game.models.TopicModel, int]]
    ],
) -> list[list[dict[str, str]]]:
    kb: list[list[dict[str, str]]] = []
    for topic, count in topics_with_counts:
        kb.append(
            [
                {
                    "text": f"🗑 {topic.title} ({count} questions)",
                    "callback_data": (
                        f"{game.constants.CallbackPrefix.DELETE_TOPIC}:{topic.id}"
                    ),
                }
            ]
        )
    kb.append(
        [
            {
                "text": "❌ Cancel",
                "callback_data": (
                    f"{game.constants.CallbackPrefix.DELETE_TOPIC}:{game.constants.Callback.CANCEL}"
                ),
            }
        ]
    )
    return kb


def topic_select_for_delete_question(
    topics_with_counts: list[
        sqlalchemy.Row[tuple[game.models.TopicModel, int]]
    ],
) -> list[list[dict[str, str]]]:
    kb: list[list[dict[str, str]]] = []
    for topic, count in topics_with_counts:
        if count > 0:
            kb.append(
                [
                    {
                        "text": f"📂 {topic.title} ({count})",
                        "callback_data": (
                            f"{game.constants.CallbackPrefix.DELETE_QUESTION_TOPIC}"
                            f":{topic.id}"
                        ),
                    }
                ]
            )
    kb.append(
        [
            {
                "text": "❌ Cancel",
                "callback_data": (
                    f"{game.constants.CallbackPrefix.DELETE_QUESTION_TOPIC}:{game.constants.Callback.CANCEL}"
                ),
            }
        ]
    )
    return kb


def _supergroup_url(chat_id: int) -> str | None:
    s = str(chat_id)
    if s.startswith("-100") and len(s) > 4:
        return f"https://t.me/c/{s[4:]}"
    return None


def dm_bot_button(
    bot_username: str,
) -> list[dict[str, str]]:
    return [
        {
            "text": "📩 Manage content in DM",
            "url": f"https://t.me/{bot_username}?start=help",
        }
    ]


def my_games_jump_buttons(
    games: list[dict[str, object]],
) -> list[list[dict[str, str]]]:
    kb: list[list[dict[str, str]]] = []
    for i, g in enumerate(games, 1):
        url = _supergroup_url(int(str(g["chat_id"])))
        if url:
            kb.append(
                [{"text": f"🔗 Jump to game #{i}", "url": url}]
            )
    return kb


def question_select_for_delete(
    questions: list[game.models.QuestionModel],
) -> list[list[dict[str, str]]]:
    kb: list[list[dict[str, str]]] = []
    for q in questions:
        label = q.text[:40] + "..." if len(q.text) > 40 else q.text
        kb.append(
            [
                {
                    "text": f"🗑 {label} ({q.cost}pts)",
                    "callback_data": (
                        f"{game.constants.CallbackPrefix.DELETE_QUESTION_CONFIRM}"
                        f":{q.id}"
                    ),
                }
            ]
        )
    kb.append(
        [
            {
                "text": "❌ Cancel",
                "callback_data": (
                    f"{game.constants.CallbackPrefix.DELETE_QUESTION_CONFIRM}"
                    f":{game.constants.Callback.CANCEL}"
                ),
            }
        ]
    )
    return kb
