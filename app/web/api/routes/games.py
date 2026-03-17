from __future__ import annotations

import typing
import uuid

import fastapi
import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import web.api.dependencies
import web.api.schemas

router = fastapi.APIRouter(prefix="/games", tags=["Games"])


@router.get("", response_model=list[web.api.schemas.GameOut])
async def list_games(
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
    status: str | None = None,
) -> list[web.api.schemas.GameOut]:
    stmt = sqlalchemy.select(game.models.GameModel).order_by(
        game.models.GameModel.created_at.desc(),
    )
    if status is not None:
        stmt = stmt.where(game.models.GameModel.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [web.api.schemas.GameOut.model_validate(g) for g in rows]


@router.get("/{game_id}", response_model=web.api.schemas.GameDetailOut)
async def get_game(
    game_id: uuid.UUID,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> web.api.schemas.GameDetailOut:
    stmt = (
        sqlalchemy.select(game.models.GameModel)
        .options(
            sqlalchemy.orm.selectinload(
                game.models.GameModel.participants
            ).joinedload(game.models.ParticipantModel.user),
        )
        .where(game.models.GameModel.id == game_id)
    )
    g = (await session.execute(stmt)).scalar_one_or_none()
    if not g:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_GAME_NOT_FOUND,
        )

    total = (
        await session.execute(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.QuestionInGameModel)
            .where(game.models.QuestionInGameModel.game_id == game_id)
        )
    ).scalar_one()
    answered = (
        await session.execute(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.QuestionInGameModel)
            .where(
                game.models.QuestionInGameModel.game_id == game_id,
                game.models.QuestionInGameModel.status
                == game.constants.QuestionInGameStatus.ANSWERED.value,
            )
        )
    ).scalar_one()

    participants = [
        web.api.schemas.ParticipantOut(
            id=p.id,
            user_id=p.user_id,
            role=p.role,
            score=p.score,
            is_active=p.is_active,
            joined_at=p.joined_at,
            username=p.user.username if p.user else None,
        )
        for p in g.participants
    ]

    return web.api.schemas.GameDetailOut(
        id=g.id,
        chat_id=g.chat_id,
        status=g.status,
        host_id=g.host_id,
        created_at=g.created_at,
        finished_at=g.finished_at,
        participants=participants,
        questions_total=total,
        questions_answered=answered,
    )
