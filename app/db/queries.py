from __future__ import annotations

import datetime
import random
import uuid

import game.models
import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.ext.asyncio


async def get_or_create_user(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    telegram_id: int,
    username: str,
) -> game.models.UserModel:
    stmt = (
        sqlalchemy.dialects.postgresql.insert(game.models.UserModel)
        .values(telegram_id=telegram_id, username=username)
        .on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={"username": username},
        )
        .returning(game.models.UserModel)
    )
    result = await s.execute(stmt)
    return result.scalar_one()


async def get_user_by_tid(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    telegram_id: int,
) -> game.models.UserModel | None:
    stmt = sqlalchemy.select(game.models.UserModel).where(
        game.models.UserModel.telegram_id == telegram_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_active_game(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    chat_id: int,
) -> game.models.GameModel | None:
    stmt = sqlalchemy.select(game.models.GameModel).where(
        game.models.GameModel.chat_id == chat_id,
        game.models.GameModel.status.in_(["waiting", "active"]),
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def create_game(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    chat_id: int,
    host_id: int,
) -> game.models.GameModel:
    g = game.models.GameModel(chat_id=chat_id, host_id=host_id)
    s.add(g)
    await s.flush()
    return g


async def games_hosted_by(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    user_id: int,
) -> list[game.models.GameModel]:
    stmt = sqlalchemy.select(game.models.GameModel).where(
        game.models.GameModel.host_id == user_id,
        game.models.GameModel.status.in_(["waiting", "active"]),
    )
    return list((await s.execute(stmt)).scalars().all())


async def is_host_anywhere(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    telegram_id: int,
) -> bool:
    user = await get_user_by_tid(s, telegram_id)
    if not user:
        return False
    stmt = (
        sqlalchemy.select(sqlalchemy.func.count())
        .select_from(game.models.GameModel)
        .where(
            game.models.GameModel.host_id == user.id,
            game.models.GameModel.status.in_(["waiting", "active"]),
        )
    )
    return (await s.execute(stmt)).scalar_one() > 0


async def add_participant(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
    user_id: int,
    role: str = "player",
) -> game.models.ParticipantModel:
    p = game.models.ParticipantModel(
        game_id=game_id, user_id=user_id, role=role
    )
    s.add(p)
    await s.flush()
    return p


async def get_participant_by_tid(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
    telegram_id: int,
) -> game.models.ParticipantModel | None:
    user = await get_user_by_tid(s, telegram_id)
    if not user:
        return None
    stmt = sqlalchemy.select(game.models.ParticipantModel).where(
        game.models.ParticipantModel.game_id == game_id,
        game.models.ParticipantModel.user_id == user.id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def get_active_players(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> list[game.models.ParticipantModel]:
    stmt = sqlalchemy.select(game.models.ParticipantModel).where(
        game.models.ParticipantModel.game_id == game_id,
        game.models.ParticipantModel.role == "player",
        game.models.ParticipantModel.is_active.is_(True),
    )
    return list((await s.execute(stmt)).scalars().all())


async def player_usernames(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> list[str]:
    stmt = (
        sqlalchemy.select(game.models.UserModel.username)
        .join(
            game.models.ParticipantModel,
            game.models.ParticipantModel.user_id == game.models.UserModel.id,
        )
        .where(
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.role == "player",
            game.models.ParticipantModel.is_active.is_(True),
        )
    )
    rows = (await s.execute(stmt)).all()
    return [r[0] or "Unknown" for r in rows]


async def scoreboard(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> list[tuple[str, int]]:
    stmt = (
        sqlalchemy.select(
            game.models.UserModel.username,
            game.models.ParticipantModel.score,
        )
        .join(
            game.models.ParticipantModel,
            game.models.ParticipantModel.user_id == game.models.UserModel.id,
        )
        .where(
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.role == "player",
        )
        .order_by(game.models.ParticipantModel.score.desc())
    )
    rows = (await s.execute(stmt)).all()
    return [(r[0] or "Unknown", r[1]) for r in rows]


async def current_player_username(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    g: game.models.GameModel,
) -> str:
    if not g.current_player_id:
        return "Unknown"
    stmt = (
        sqlalchemy.select(game.models.UserModel.username)
        .join(
            game.models.ParticipantModel,
            game.models.ParticipantModel.user_id == game.models.UserModel.id,
        )
        .where(game.models.ParticipantModel.id == g.current_player_id)
    )
    row = (await s.execute(stmt)).one_or_none()
    return row[0] if row else "Unknown"


async def pick_random_player(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> game.models.ParticipantModel | None:
    players = await get_active_players(s, game_id)
    return random.choice(players) if players else None


async def get_user_by_id(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    user_id: int,
) -> game.models.UserModel | None:
    stmt = sqlalchemy.select(game.models.UserModel).where(
        game.models.UserModel.id == user_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def create_topic(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    title: str,
) -> game.models.TopicModel:
    t = game.models.TopicModel(title=title)
    s.add(t)
    await s.flush()
    return t


async def get_topic_by_title(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    title: str,
) -> game.models.TopicModel | None:
    stmt = sqlalchemy.select(game.models.TopicModel).where(
        game.models.TopicModel.title == title,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def all_topics(
    s: sqlalchemy.ext.asyncio.AsyncSession,
) -> list[game.models.TopicModel]:
    stmt = sqlalchemy.select(game.models.TopicModel).order_by(
        game.models.TopicModel.title,
    )
    return list((await s.execute(stmt)).scalars().all())


async def delete_topic(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    topic_id: uuid.UUID,
) -> int:
    cnt = (
        await s.execute(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.QuestionModel)
            .where(game.models.QuestionModel.topic_id == topic_id),
        )
    ).scalar_one()
    await s.execute(
        sqlalchemy.delete(game.models.TopicModel).where(
            game.models.TopicModel.id == topic_id
        ),
    )
    return cnt


async def create_question(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    topic_id: uuid.UUID,
    text: str,
    answer: str,
    cost: int,
) -> game.models.QuestionModel:
    q = game.models.QuestionModel(
        topic_id=topic_id,
        text=text,
        answer=answer,
        cost=cost,
    )
    s.add(q)
    await s.flush()
    return q


async def questions_by_topic(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    topic_id: uuid.UUID,
) -> list[game.models.QuestionModel]:
    stmt = (
        sqlalchemy.select(game.models.QuestionModel)
        .where(game.models.QuestionModel.topic_id == topic_id)
        .order_by(game.models.QuestionModel.cost)
    )
    return list((await s.execute(stmt)).scalars().all())


async def all_question_ids(
    s: sqlalchemy.ext.asyncio.AsyncSession,
) -> list[uuid.UUID]:
    stmt = sqlalchemy.select(game.models.QuestionModel.id)
    return [r[0] for r in (await s.execute(stmt)).all()]


async def delete_question(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    question_id: uuid.UUID,
) -> bool:
    res = await s.execute(
        sqlalchemy.delete(game.models.QuestionModel).where(
            game.models.QuestionModel.id == question_id
        ),
    )
    return res.rowcount > 0


async def question_count_by_topic(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    topic_id: uuid.UUID,
) -> int:
    return (
        await s.execute(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.QuestionModel)
            .where(game.models.QuestionModel.topic_id == topic_id),
        )
    ).scalar_one()


async def bulk_create_qig(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
    question_ids: list[uuid.UUID],
) -> None:
    for qid in question_ids:
        s.add(game.models.QuestionInGameModel(game_id=game_id, question_id=qid))
    await s.flush()


async def pending_board(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> list[tuple]:
    qig = game.models.QuestionInGameModel
    q = game.models.QuestionModel
    t = game.models.TopicModel
    stmt = (
        sqlalchemy.select(qig.id, t.title, q.cost, q.text, q.answer)
        .join(q, qig.question_id == q.id)
        .join(t, q.topic_id == t.id)
        .where(qig.game_id == game_id, qig.status == "pending")
        .order_by(t.title, q.cost)
    )
    return list((await s.execute(stmt)).all())


async def get_qig_detail(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    qig_id: uuid.UUID,
) -> tuple | None:
    qig = game.models.QuestionInGameModel
    q = game.models.QuestionModel
    t = game.models.TopicModel
    stmt = (
        sqlalchemy.select(qig, t.title, q.text, q.answer, q.cost)
        .join(q, qig.question_id == q.id)
        .join(t, q.topic_id == t.id)
        .where(qig.id == qig_id)
    )
    return (await s.execute(stmt)).one_or_none()


async def create_game_state(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
    status: str,
) -> game.models.GameStateModel:
    gs = game.models.GameStateModel(game_id=game_id, status=status)
    s.add(gs)
    await s.flush()
    return gs


async def get_game_state(
    s: sqlalchemy.ext.asyncio.AsyncSession,
    game_id: uuid.UUID,
) -> game.models.GameStateModel | None:
    stmt = sqlalchemy.select(game.models.GameStateModel).where(
        game.models.GameStateModel.game_id == game_id,
    )
    return (await s.execute(stmt)).scalar_one_or_none()


async def claim_expired_timer(
    s: sqlalchemy.ext.asyncio.AsyncSession,
) -> tuple[game.models.GameStateModel, int] | None:
    now = datetime.datetime.now(datetime.UTC)
    gs_m = game.models.GameStateModel
    gm = game.models.GameModel
    stmt = (
        sqlalchemy.select(gs_m, gm.chat_id)
        .join(gm, gs_m.game_id == gm.id)
        .where(
            gs_m.timer_ends_at.isnot(None),
            gs_m.timer_ends_at <= now,
            gm.status == "active",
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = (await s.execute(stmt)).one_or_none()
    if row is None:
        return None
    gs, chat_id = row
    gs.timer_ends_at = None
    return gs, chat_id
