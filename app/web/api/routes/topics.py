from __future__ import annotations

import typing
import uuid

import fastapi
import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import web.api.dependencies
import web.api.schemas

router = fastapi.APIRouter(prefix="/topics", tags=["Topics"])


@router.get("", response_model=list[web.api.schemas.TopicWithCountOut])
async def list_topics(
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> list[web.api.schemas.TopicWithCountOut]:
    stmt = (
        sqlalchemy.select(
            game.models.TopicModel,
            sqlalchemy.func.count(game.models.QuestionModel.id).label(
                "question_count"
            ),
        )
        .outerjoin(
            game.models.QuestionModel,
            game.models.QuestionModel.topic_id == game.models.TopicModel.id,
        )
        .group_by(game.models.TopicModel.id)
        .order_by(game.models.TopicModel.title)
    )
    rows = (await session.execute(stmt)).all()
    return [
        web.api.schemas.TopicWithCountOut(
            id=topic.id,
            title=topic.title,
            is_visible=topic.is_visible,
            question_count=count,
        )
        for topic, count in rows
    ]


@router.post(
    "",
    response_model=web.api.schemas.TopicOut,
    status_code=201,
)
async def create_topic(
    body: web.api.schemas.TopicCreate,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> game.models.TopicModel:
    existing = (
        await session.execute(
            sqlalchemy.select(game.models.TopicModel).where(
                game.models.TopicModel.title == body.title,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise fastapi.HTTPException(
            status_code=409,
            detail=game.constants.API_MSG_TOPIC_ALREADY_EXISTS.format(
                body.title
            ),
        )
    topic = game.models.TopicModel(title=body.title)
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


@router.put("/{topic_id}", response_model=web.api.schemas.TopicOut)
async def update_topic(
    topic_id: uuid.UUID,
    body: web.api.schemas.TopicUpdate,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> game.models.TopicModel:
    topic = await session.get(game.models.TopicModel, topic_id)
    if not topic:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_TOPIC_NOT_FOUND,
        )

    dup = (
        await session.execute(
            sqlalchemy.select(game.models.TopicModel).where(
                game.models.TopicModel.title == body.title,
                game.models.TopicModel.id != topic_id,
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise fastapi.HTTPException(
            status_code=409,
            detail=game.constants.API_MSG_TOPIC_ALREADY_EXISTS.format(
                body.title
            ),
        )

    topic.title = body.title
    await session.commit()
    await session.refresh(topic)
    return topic


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: uuid.UUID,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> fastapi.Response:
    topic = await session.get(game.models.TopicModel, topic_id)
    if not topic:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_TOPIC_NOT_FOUND,
        )

    question_ids = [
        row[0]
        for row in (
            await session.execute(
                sqlalchemy.select(game.models.QuestionModel.id).where(
                    game.models.QuestionModel.topic_id == topic_id,
                )
            )
        ).all()
    ]

    if question_ids:
        qig_ids = [
            row[0]
            for row in (
                await session.execute(
                    sqlalchemy.select(game.models.QuestionInGameModel.id).where(
                        game.models.QuestionInGameModel.question_id.in_(
                            question_ids
                        ),
                    )
                )
            ).all()
        ]
        if qig_ids:
            await session.execute(
                sqlalchemy.delete(game.models.GameItemUsageModel).where(
                    game.models.GameItemUsageModel.question_in_game_id.in_(
                        qig_ids
                    ),
                )
            )
            await session.execute(
                sqlalchemy.update(game.models.GameStateModel)
                .where(
                    game.models.GameStateModel.current_question_id.in_(qig_ids),
                )
                .values(current_question_id=None)
            )
            await session.execute(
                sqlalchemy.delete(game.models.QuestionInGameModel).where(
                    game.models.QuestionInGameModel.question_id.in_(
                        question_ids
                    ),
                )
            )
        await session.execute(
            sqlalchemy.delete(game.models.QuestionModel).where(
                game.models.QuestionModel.topic_id == topic_id,
            )
        )

    await session.execute(
        sqlalchemy.delete(game.models.TopicModel).where(
            game.models.TopicModel.id == topic_id,
        )
    )
    await session.commit()
    return fastapi.Response(status_code=204)
