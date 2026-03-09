from __future__ import annotations

import datetime
import logging
import uuid

import db.queries
import game.models
import game.schemas
import sqlalchemy
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)

DB_ERROR_MSG = "⚠️ Bot is temporarily unavailable. Please try again later."


class GameLogic:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
        buzzer_timeout: int = 10,
        answer_timeout: int = 15,
    ):
        self._sf = session_factory
        self._buzzer_timeout = buzzer_timeout
        self._answer_timeout = answer_timeout

    def _resp(
        self, chat_id: int, text: str, **kw: object
    ) -> game.schemas.GameResponse:
        return game.schemas.GameResponse(chat_id=chat_id, text=text, **kw)

    @staticmethod
    def _lobby_kb() -> list[list[dict]]:
        return [
            [
                {"text": "🎮 Join", "callback_data": "join"},
                {"text": "👀 Spectate", "callback_data": "spectate"},
            ],
            [
                {"text": "📖 Rules", "callback_data": "rules"},
                {"text": "❓ Help", "callback_data": "help"},
            ],
        ]

    @staticmethod
    def _buzzer_kb() -> list[list[dict]]:
        return [[{"text": "🔔 Buzzer", "callback_data": "buzzer"}]]

    @staticmethod
    def _score_kb() -> list[list[dict]]:
        return [
            [
                {"text": "🚪 Leave", "callback_data": "leave"},
                {"text": "⏹ Stop", "callback_data": "stop"},
            ]
        ]

    @staticmethod
    def _build_board_text(rows: list[tuple]) -> str:
        by_topic: dict[str, list[int]] = {}
        for _qig_id, topic, cost, _text, _answer in rows:
            by_topic.setdefault(topic, []).append(cost)
        lines: list[str] = []
        for topic, costs in by_topic.items():
            lines.append(
                f"{topic}: {' | '.join(str(c) for c in sorted(costs))}"
            )
        return "\n".join(lines) if lines else "No questions remaining."

    @staticmethod
    def _build_board_kb(rows: list[tuple]) -> list[list[dict]]:
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
                        "callback_data": f"q:{qig_id}",
                    }
                )
            kb.append(row)
        return kb

    async def handle_start(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            user = await db.queries.get_or_create_user(s, telegram_id, username)
            existing = await db.queries.get_active_game(s, chat_id)
            if existing:
                return [
                    self._resp(
                        chat_id,
                        f"A game already exists (status: {existing.status}).",
                        keyboard=self._lobby_kb(),
                    )
                ]
            g = await db.queries.create_game(s, chat_id, user.id)
            await db.queries.add_participant(s, g.id, user.id, "player")
            await db.queries.create_game_state(s, g.id, "lobby")
            logger.info("Game created in chat %d by %s", chat_id, username)
            return [
                self._resp(
                    chat_id,
                    f"🎮 Game created! {username} is the host.\n"
                    "Use buttons below to join.",
                    keyboard=self._lobby_kb(),
                )
            ]

    async def handle_start_game(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [
                    self._resp(chat_id, "No game in this chat. Use /start.")
                ]
            user = await db.queries.get_user_by_tid(s, telegram_id)
            if not user or g.host_id != user.id:
                return [
                    self._resp(chat_id, "Only the host can start the game.")
                ]
            if g.status != "waiting":
                return [self._resp(chat_id, "Game is not in waiting state.")]

            players = await db.queries.get_active_players(s, g.id)
            if len(players) < 2:
                return [
                    self._resp(chat_id, "Need at least 2 players to start.")
                ]

            q_ids = await db.queries.all_question_ids(s)
            if not q_ids:
                return [
                    self._resp(
                        chat_id,
                        "No questions available! Add topics and "
                        "questions first (use /add_topic in DM).",
                    )
                ]

            await db.queries.bulk_create_qig(s, g.id, q_ids)
            first = await db.queries.pick_random_player(s, g.id)
            g.current_player_id = first.id
            g.status = "active"

            gs = await db.queries.get_game_state(s, g.id)
            gs.status = "choosing_question"

            pending = await db.queries.pending_board(s, g.id)
            cp_name = await db.queries.current_player_username(s, g)
            logger.info(
                "Game started in chat %d (%d questions)", chat_id, len(q_ids)
            )

            return [
                self._resp(
                    chat_id,
                    f"🎯 Game started! {cp_name} picks first.\n\n"
                    f"{self._build_board_text(pending)}",
                    keyboard=self._build_board_kb(pending),
                )
            ]

    async def handle_stop(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [self._resp(chat_id, "No game in this chat.")]
            user = await db.queries.get_user_by_tid(s, telegram_id)
            if not user or g.host_id != user.id:
                return [self._resp(chat_id, "Only the host can stop the game.")]
            return await self._finish_game(s, g, chat_id, stopped=True)

    async def handle_score(
        self, chat_id: int
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [self._resp(chat_id, "No game in this chat.")]
            sb = await db.queries.scoreboard(s, g.id)
            lines = ["📊 Scoreboard:"]
            for i, (name, score) in enumerate(sb, 1):
                lines.append(f"{i}. {name}: {score}")
            return [
                self._resp(chat_id, "\n".join(lines), keyboard=self._score_kb())
            ]

    async def handle_join(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [
                    self._resp(chat_id, "No game in this chat. Use /start.")
                ]
            if g.status != "waiting":
                return [self._resp(chat_id, "Game already in progress.")]
            user = await db.queries.get_or_create_user(s, telegram_id, username)
            existing = await db.queries.get_participant_by_tid(
                s, g.id, telegram_id
            )
            if existing:
                return [self._resp(chat_id, f"{username}, you already joined!")]
            await db.queries.add_participant(s, g.id, user.id, "player")
            names = await db.queries.player_usernames(s, g.id)
            logger.info("%s joined game in chat %d", username, chat_id)
            return [
                self._resp(
                    chat_id,
                    f"🎮 {username} joined! Players: {len(names)}\n"
                    f"Roster: {', '.join(names)}",
                    keyboard=self._lobby_kb(),
                )
            ]

    async def handle_spectate(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [
                    self._resp(chat_id, "No game in this chat. Use /start.")
                ]
            user = await db.queries.get_or_create_user(s, telegram_id, username)
            existing = await db.queries.get_participant_by_tid(
                s, g.id, telegram_id
            )
            if existing:
                if existing.role == "spectator":
                    return [
                        self._resp(
                            chat_id, f"{username}, you are already spectating!"
                        )
                    ]
                return [
                    self._resp(
                        chat_id, f"{username}, you are already a player!"
                    )
                ]
            await db.queries.add_participant(s, g.id, user.id, "spectator")
            logger.info("%s spectating in chat %d", username, chat_id)
            return [self._resp(chat_id, f"👀 {username} is now spectating.")]

    async def handle_leave(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g:
                return [self._resp(chat_id, "No game in this chat.")]
            user = await db.queries.get_or_create_user(s, telegram_id, username)
            p = await db.queries.get_participant_by_tid(s, g.id, telegram_id)
            if not p:
                return [self._resp(chat_id, "You are not in this game.")]

            if g.status == "active":
                p.is_active = False
                if g.current_player_id == p.id:
                    new_cp = await db.queries.pick_random_player(s, g.id)
                    g.current_player_id = new_cp.id if new_cp else None
            else:
                await s.delete(p)

            if g.host_id == user.id:
                active = await db.queries.get_active_players(s, g.id)
                remaining = [a for a in active if a.id != p.id]
                if remaining:
                    g.host_id = remaining[0].user_id
                    nh = await db.queries.get_user_by_id(
                        s, remaining[0].user_id
                    )
                    nh_name = nh.username if nh else "Unknown"
                    return [
                        self._resp(
                            chat_id,
                            f"{username} left. {nh_name} is the new host.",
                        )
                    ]
                g.status = "finished"
                gs = await db.queries.get_game_state(s, g.id)
                if gs:
                    gs.status = "finished"
                return [
                    self._resp(
                        chat_id,
                        "Host left and no players remain. Game disbanded.",
                    )
                ]

            logger.info("%s left game in chat %d", username, chat_id)
            return [self._resp(chat_id, f"{username} left the game.")]

    async def handle_buzzer(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g or g.status != "active":
                return [self._resp(chat_id, "No active game.")]
            gs = await db.queries.get_game_state(s, g.id)
            if not gs or gs.status != "waiting_buzzer":
                return [self._resp(chat_id, "Buzzer is not active right now.")]
            p = await db.queries.get_participant_by_tid(s, g.id, telegram_id)
            if not p:
                return [self._resp(chat_id, "You are not in this game.")]
            if p.role != "player":
                return [
                    self._resp(chat_id, "Spectators cannot press the buzzer.")
                ]

            now = datetime.datetime.now(datetime.UTC)
            gs.buzzer_pressed_by = p.id
            gs.buzzer_pressed_at = now
            gs.status = "waiting_answer"
            gs.timer_ends_at = now + datetime.timedelta(
                seconds=self._answer_timeout
            )

            logger.info("%s pressed buzzer in chat %d", username, chat_id)
            return [
                self._resp(
                    chat_id,
                    f"🔔 {username} pressed the buzzer!\n"
                    f"Type your answer ({self._answer_timeout}s)...",
                )
            ]

    async def handle_question_selected(
        self,
        chat_id: int,
        telegram_id: int,
        qig_id_str: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g or g.status != "active":
                return [self._resp(chat_id, "No active game.")]
            gs = await db.queries.get_game_state(s, g.id)
            if not gs or gs.status != "choosing_question":
                return [self._resp(chat_id, "Not in question selection phase.")]
            p = await db.queries.get_participant_by_tid(s, g.id, telegram_id)
            if not p or g.current_player_id != p.id:
                cp_name = await db.queries.current_player_username(s, g)
                return [
                    self._resp(
                        chat_id, f"Only {cp_name} can pick a question now."
                    )
                ]

            try:
                qig_id = uuid.UUID(qig_id_str)
            except ValueError:
                qig_id = None
            detail = (
                await db.queries.get_qig_detail(s, qig_id) if qig_id else None
            )
            if not detail or detail[0].status != "pending":
                return [self._resp(chat_id, "Question not found.")]
            qig, topic, q_text, _answer, cost = detail

            now = datetime.datetime.now(datetime.UTC)
            qig.status = "asked"
            qig.asked_by = p.id
            qig.asked_at = now
            gs.current_question_id = qig.id
            gs.status = "waiting_buzzer"
            gs.timer_ends_at = now + datetime.timedelta(
                seconds=self._buzzer_timeout
            )

            return [
                self._resp(
                    chat_id,
                    f"📋 {topic} for {cost}\n\n{q_text}\n\n"
                    f"Press the buzzer to answer! ({self._buzzer_timeout}s)",
                    keyboard=self._buzzer_kb(),
                )
            ]

    async def handle_possible_answer(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        text: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            g = await db.queries.get_active_game(s, chat_id)
            if not g or g.status != "active":
                return []
            gs = await db.queries.get_game_state(s, g.id)
            if (
                not gs
                or gs.status != "waiting_answer"
                or not gs.buzzer_pressed_by
            ):
                return []
            user = await db.queries.get_user_by_tid(s, telegram_id)
            if not user:
                return []
            bp_stmt = sqlalchemy.select(game.models.ParticipantModel).where(
                game.models.ParticipantModel.id == gs.buzzer_pressed_by,
                game.models.ParticipantModel.user_id == user.id,
            )
            bp = (await s.execute(bp_stmt)).scalar_one_or_none()
            if not bp:
                return []
            return await self._process_answer(s, g, gs, bp, username, text)

    async def handle_help(
        self, chat_id: int
    ) -> list[game.schemas.GameResponse]:
        text = (
            "❓ How to play:\n\n"
            "Commands:\n"
            "/start — Create a new game\n"
            "/start_game — Start the game (host)\n"
            "/score — Show scoreboard\n\n"
            "Everything else uses inline buttons:\n"
            "🎮 Join / 👀 Spectate / 🚪 Leave\n"
            "🔔 Buzzer — press to answer\n"
            "Just type your answer when you buzz in!\n\n"
            "Private chat with bot:\n"
            "/add_topic — Create a topic\n"
            "/add_question — Add a question\n"
            "/delete_topic / /delete_question — Remove content\n"
            "/my_games — Your hosted games"
        )
        return [self._resp(chat_id, text)]

    async def handle_rules(
        self, chat_id: int
    ) -> list[game.schemas.GameResponse]:
        text = (
            "📖 SI Game Rules:\n\n"
            "1. Host creates a game with /start, players join via buttons.\n"
            "2. Host starts with /start_game. A random player picks first.\n"
            "3. Current player selects a topic and cost from the board.\n"
            "4. The question appears. Press 🔔 Buzzer to answer.\n"
            f"5. First to buzz has {self._answer_timeout}s to answer.\n"
            "6. Correct → +points, you pick next. Wrong → −points.\n"
            f"7. No buzz within {self._buzzer_timeout}s → question burns.\n"
            "8. Game ends when all questions are answered.\n"
            "9. Highest score wins! 🏆"
        )
        return [self._resp(chat_id, text)]

    async def handle_my_games(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            user = await db.queries.get_user_by_tid(s, telegram_id)
            if not user:
                return [self._resp(chat_id, "You are not hosting any games.")]
            games = await db.queries.games_hosted_by(s, user.id)
            if not games:
                return [self._resp(chat_id, "You are not hosting any games.")]
            lines = ["Your games:"]
            for gm in games:
                pc = len(await db.queries.get_active_players(s, gm.id))
                lines.append(
                    f"• Chat {gm.chat_id} — {gm.status} ({pc} players)"
                )
            return [self._resp(chat_id, "\n".join(lines))]

    async def handle_add_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_name: str,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            if not await db.queries.is_host_anywhere(s, telegram_id):
                return [
                    self._resp(
                        chat_id, "You must be a host of at least one game."
                    )
                ]
            existing = await db.queries.get_topic_by_title(s, topic_name)
            if existing:
                return [
                    self._resp(chat_id, f'Topic "{topic_name}" already exists.')
                ]
            await db.queries.create_topic(s, topic_name)
            logger.info('Topic "%s" added by user %d', topic_name, telegram_id)
            return [
                self._resp(
                    chat_id,
                    f'✅ Topic "{topic_name}" added.\n'
                    "Use /add_question to add questions.",
                )
            ]

    async def handle_add_question(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
        text: str,
        answer: str,
        cost: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            if not await db.queries.is_host_anywhere(s, telegram_id):
                return [
                    self._resp(chat_id, "You must be a host to add questions.")
                ]
            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [self._resp(chat_id, "Invalid topic.")]
            if cost <= 0:
                return [self._resp(chat_id, "Cost must be positive.")]
            await db.queries.create_question(s, topic_id, text, answer, cost)
            cnt = await db.queries.question_count_by_topic(s, topic_id)
            logger.info(
                "Question added (topic_id=%s, cost=%d)", topic_id_str, cost
            )
            return [
                self._resp(
                    chat_id,
                    f"✅ Question added for {cost} points ({cnt} in topic).\n"
                    "Send /add_question to add more, or /done to finish.",
                )
            ]

    async def topic_keyboard_for_add(
        self,
        chat_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            topics = await db.queries.all_topics(s)
            if not topics:
                return [
                    self._resp(
                        chat_id, "No topics yet. Create one with /add_topic."
                    )
                ]
            kb: list[list[dict]] = [
                [{"text": t.title, "callback_data": f"addq_topic:{t.id}"}]
                for t in topics
            ]
            kb.append(
                [{"text": "❌ Cancel", "callback_data": "addq_topic:cancel"}]
            )
            return [
                self._resp(
                    chat_id,
                    "Select a topic for the new question:",
                    keyboard=kb,
                )
            ]

    async def handle_delete_topic(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            if not await db.queries.is_host_anywhere(s, telegram_id):
                return [
                    self._resp(chat_id, "You must be a host to delete topics.")
                ]
            topics = await db.queries.all_topics(s)
            if not topics:
                return [self._resp(chat_id, "No topics exist.")]
            kb: list[list[dict]] = []
            for t in topics:
                cnt = await db.queries.question_count_by_topic(s, t.id)
                kb.append(
                    [
                        {
                            "text": f"🗑 {t.title} ({cnt} questions)",
                            "callback_data": f"del_topic:{t.id}",
                        }
                    ]
                )
            kb.append(
                [{"text": "❌ Cancel", "callback_data": "del_topic:cancel"}]
            )
            return [
                self._resp(chat_id, "Select a topic to delete:", keyboard=kb)
            ]

    async def confirm_delete_topic(
        self,
        chat_id: int,
        telegram_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.GameResponse]:
        if topic_id_str == "cancel":
            return [self._resp(chat_id, "Deletion cancelled.")]
        async with self._sf() as s, s.begin():
            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [self._resp(chat_id, "Invalid topic.")]
            cnt = await db.queries.delete_topic(s, topic_id)
            logger.info(
                "Topic %s deleted (%d questions removed)", topic_id_str, cnt
            )
            return [
                self._resp(
                    chat_id, f"✅ Topic deleted ({cnt} questions removed)."
                )
            ]

    async def handle_delete_question(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            if not await db.queries.is_host_anywhere(s, telegram_id):
                return [
                    self._resp(
                        chat_id, "You must be a host to delete questions."
                    )
                ]
            topics = await db.queries.all_topics(s)
            if not topics:
                return [self._resp(chat_id, "No topics exist.")]
            kb: list[list[dict]] = []
            for t in topics:
                cnt = await db.queries.question_count_by_topic(s, t.id)
                if cnt > 0:
                    kb.append(
                        [
                            {
                                "text": f"📂 {t.title} ({cnt})",
                                "callback_data": f"delq_topic:{t.id}",
                            }
                        ]
                    )
            if not kb:
                return [self._resp(chat_id, "No questions to delete.")]
            kb.append(
                [{"text": "❌ Cancel", "callback_data": "delq_topic:cancel"}]
            )
            return [self._resp(chat_id, "Select a topic:", keyboard=kb)]

    async def list_questions_for_delete(
        self,
        chat_id: int,
        topic_id_str: str,
    ) -> list[game.schemas.GameResponse]:
        if topic_id_str == "cancel":
            return [self._resp(chat_id, "Deletion cancelled.")]
        async with self._sf() as s, s.begin():
            try:
                topic_id = uuid.UUID(topic_id_str)
            except ValueError:
                return [self._resp(chat_id, "Invalid topic.")]
            questions = await db.queries.questions_by_topic(s, topic_id)
            if not questions:
                return [self._resp(chat_id, "No questions in this topic.")]
            kb: list[list[dict]] = []
            for q in questions:
                label = q.text[:40] + "..." if len(q.text) > 40 else q.text
                kb.append(
                    [
                        {
                            "text": f"🗑 {label} ({q.cost}pts)",
                            "callback_data": f"delq_confirm:{q.id}",
                        }
                    ]
                )
            kb.append(
                [{"text": "❌ Cancel", "callback_data": "delq_confirm:cancel"}]
            )
            return [
                self._resp(chat_id, "Select a question to delete:", keyboard=kb)
            ]

    async def confirm_delete_question(
        self,
        chat_id: int,
        telegram_id: int,
        question_id_str: str,
    ) -> list[game.schemas.GameResponse]:
        if question_id_str == "cancel":
            return [self._resp(chat_id, "Deletion cancelled.")]
        async with self._sf() as s, s.begin():
            try:
                question_id = uuid.UUID(question_id_str)
            except ValueError:
                return [self._resp(chat_id, "Invalid question.")]
            deleted = await db.queries.delete_question(s, question_id)
            if not deleted:
                return [self._resp(chat_id, "Question not found.")]
            logger.info("Question %s deleted", question_id_str)
            return [self._resp(chat_id, "✅ Question deleted.")]

    async def check_timers(self) -> list[game.schemas.GameResponse]:
        async with self._sf() as s, s.begin():
            result = await db.queries.claim_expired_timer(s)
            if result is None:
                return []
            gs, chat_id = result
            g_stmt = sqlalchemy.select(game.models.GameModel).where(
                game.models.GameModel.id == gs.game_id,
            )
            g = (await s.execute(g_stmt)).scalar_one()

            if gs.status == "waiting_buzzer":
                return await self._handle_buzzer_timeout(s, g, gs, chat_id)
            if gs.status == "waiting_answer":
                return await self._handle_answer_timeout(s, g, gs, chat_id)
            return []

    async def _process_answer(
        self,
        s: sqlalchemy.ext.asyncio.AsyncSession,
        g: game.models.GameModel,
        gs: game.models.GameStateModel,
        bp: game.models.ParticipantModel,
        username: str,
        answer_text: str,
    ) -> list[game.schemas.GameResponse]:
        if not gs.current_question_id:
            return []
        detail = await db.queries.get_qig_detail(s, gs.current_question_id)
        if not detail:
            return []
        qig, _topic, _q_text, correct_answer, cost = detail

        given = answer_text.strip().lower()
        correct = correct_answer.strip().lower()

        if given == correct:
            bp.score += cost
            qig.status = "answered"
            qig.answered_by = bp.id
            qig.answered_at = datetime.datetime.now(datetime.UTC)
            g.current_player_id = bp.id
            result_text = (
                f"✅ Correct! {username} gets +{cost} "
                f"points (total: {bp.score})."
            )
            logger.info(
                "%s answered correctly in chat %d (+%d)",
                username,
                g.chat_id,
                cost,
            )
        else:
            bp.score -= cost
            qig.status = "answered"
            result_text = (
                f"❌ Wrong! Correct answer: {correct_answer}\n"
                f"{username} loses {cost} points (total: {bp.score})."
            )
            logger.info(
                "%s answered wrong in chat %d (-%d)", username, g.chat_id, cost
            )

        gs.current_question_id = None
        gs.buzzer_pressed_by = None
        gs.buzzer_pressed_at = None
        gs.timer_ends_at = None

        responses: list[game.schemas.GameResponse] = [
            self._resp(g.chat_id, result_text)
        ]
        responses.extend(await self._next_round_or_finish(s, g, gs, g.chat_id))
        return responses

    async def _handle_buzzer_timeout(
        self,
        s: sqlalchemy.ext.asyncio.AsyncSession,
        g: game.models.GameModel,
        gs: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.GameResponse]:
        if not gs.current_question_id:
            return []
        detail = await db.queries.get_qig_detail(s, gs.current_question_id)
        if not detail:
            return []
        qig, _topic, _text, answer, _cost = detail
        qig.status = "answered"
        gs.current_question_id = None
        gs.buzzer_pressed_by = None

        responses: list[game.schemas.GameResponse] = [
            self._resp(
                chat_id,
                f"⏰ Time is up! No one buzzed.\nCorrect answer: {answer}",
            ),
        ]
        responses.extend(await self._next_round_or_finish(s, g, gs, chat_id))
        return responses

    async def _handle_answer_timeout(
        self,
        s: sqlalchemy.ext.asyncio.AsyncSession,
        g: game.models.GameModel,
        gs: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.GameResponse]:
        if not gs.current_question_id:
            return []
        detail = await db.queries.get_qig_detail(s, gs.current_question_id)
        if not detail:
            return []
        qig, _topic, _text, answer, cost = detail

        if gs.buzzer_pressed_by:
            bp_stmt = sqlalchemy.select(game.models.ParticipantModel).where(
                game.models.ParticipantModel.id == gs.buzzer_pressed_by,
            )
            bp = (await s.execute(bp_stmt)).scalar_one_or_none()
            if bp:
                bp.score -= cost

        qig.status = "answered"
        gs.current_question_id = None
        gs.buzzer_pressed_by = None
        gs.buzzer_pressed_at = None

        responses: list[game.schemas.GameResponse] = [
            self._resp(chat_id, f"⏰ Time is up! Correct answer: {answer}"),
        ]
        responses.extend(await self._next_round_or_finish(s, g, gs, chat_id))
        return responses

    async def _next_round_or_finish(
        self,
        s: sqlalchemy.ext.asyncio.AsyncSession,
        g: game.models.GameModel,
        gs: game.models.GameStateModel,
        chat_id: int,
    ) -> list[game.schemas.GameResponse]:
        pending = await db.queries.pending_board(s, g.id)
        if not pending:
            return await self._finish_game(s, g, chat_id)
        gs.status = "choosing_question"
        gs.timer_ends_at = None
        cp_name = await db.queries.current_player_username(s, g)
        return [
            self._resp(
                chat_id,
                f"{cp_name}, pick the next question!\n\n"
                f"{self._build_board_text(pending)}",
                keyboard=self._build_board_kb(pending),
            )
        ]

    async def _finish_game(
        self,
        s: sqlalchemy.ext.asyncio.AsyncSession,
        g: game.models.GameModel,
        chat_id: int,
        *,
        stopped: bool = False,
    ) -> list[game.schemas.GameResponse]:
        g.status = "finished"
        g.finished_at = datetime.datetime.now(datetime.UTC)
        gs = await db.queries.get_game_state(s, g.id)
        if gs:
            gs.status = "finished"

        sb = await db.queries.scoreboard(s, g.id)
        prefix = "Game stopped by host." if stopped else "🏁 Game over!"
        lines = [f"{prefix}\n\nFinal scores:"]
        for i, (name, score) in enumerate(sb, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"{medal} {name}: {score}")
        logger.info("Game finished in chat %d", chat_id)
        return [self._resp(chat_id, "\n".join(lines))]
