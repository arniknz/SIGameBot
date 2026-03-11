from __future__ import annotations

import game.constants


def lobby() -> list[list[dict]]:
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


def buzzer() -> list[list[dict]]:
    return [
        [
            {
                "text": "🔔 Buzzer",
                "callback_data": game.constants.Callback.BUZZER,
            }
        ]
    ]


def score() -> list[list[dict]]:
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


def board(rows: list[tuple]) -> list[list[dict]]:
    by_topic: dict[str, list[tuple]] = {}
    for qig_id, topic, cost, _text, _answer in rows:
        by_topic.setdefault(topic, []).append((qig_id, cost))
    kb: list[list[dict]] = []
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


def board_text(rows: list[tuple]) -> str:
    by_topic: dict[str, list[int]] = {}
    for _qig_id, topic, cost, _text, _answer in rows:
        by_topic.setdefault(topic, []).append(cost)
    lines: list[str] = []
    for topic, costs in by_topic.items():
        lines.append(f"{topic}: {' | '.join(str(c) for c in sorted(costs))}")
    return "\n".join(lines) if lines else "No questions remaining."


def topic_select_for_add(topics: list) -> list[list[dict]]:
    kb: list[list[dict]] = [
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
                    f"{game.constants.CallbackPrefix.ADD_QUESTION_TOPIC}:cancel"
                ),
            }
        ]
    )
    return kb


def topic_select_for_delete(
    topics_with_counts: list[tuple],
) -> list[list[dict]]:
    kb: list[list[dict]] = []
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
                    f"{game.constants.CallbackPrefix.DELETE_TOPIC}:cancel"
                ),
            }
        ]
    )
    return kb


def topic_select_for_delete_question(
    topics_with_counts: list[tuple],
) -> list[list[dict]]:
    kb: list[list[dict]] = []
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
                    f"{game.constants.CallbackPrefix.DELETE_QUESTION_TOPIC}:cancel"
                ),
            }
        ]
    )
    return kb


def question_select_for_delete(questions: list) -> list[list[dict]]:
    kb: list[list[dict]] = []
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
                    ":cancel"
                ),
            }
        ]
    )
    return kb
