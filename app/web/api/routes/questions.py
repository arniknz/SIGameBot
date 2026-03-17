from __future__ import annotations

import csv
import io
import typing
import uuid

import fastapi
import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import web.api.dependencies
import web.api.schemas

router = fastapi.APIRouter(prefix="/questions", tags=["Questions"])


@router.get("", response_model=list[web.api.schemas.QuestionOut])
async def list_questions(
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
    topic_id: uuid.UUID | None = None,
) -> list[web.api.schemas.QuestionOut]:
    stmt = (
        sqlalchemy.select(
            game.models.QuestionModel,
            game.models.TopicModel.title.label("topic_title"),
        )
        .join(
            game.models.TopicModel,
            game.models.QuestionModel.topic_id == game.models.TopicModel.id,
        )
        .order_by(game.models.TopicModel.title, game.models.QuestionModel.cost)
    )
    if topic_id is not None:
        stmt = stmt.where(game.models.QuestionModel.topic_id == topic_id)

    rows = (await session.execute(stmt)).all()
    return [
        web.api.schemas.QuestionOut(
            id=q.id,
            topic_id=q.topic_id,
            text=q.text,
            answer=q.answer,
            cost=q.cost,
            is_visible=q.is_visible,
            topic_title=title,
        )
        for q, title in rows
    ]


@router.post(
    "",
    response_model=web.api.schemas.QuestionOut,
    status_code=201,
)
async def create_question(
    body: web.api.schemas.QuestionCreate,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> web.api.schemas.QuestionOut:
    topic = await session.get(game.models.TopicModel, body.topic_id)
    if not topic:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_TOPIC_NOT_FOUND,
        )

    question = game.models.QuestionModel(
        topic_id=body.topic_id,
        text=body.text,
        answer=body.answer,
        cost=body.cost,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return web.api.schemas.QuestionOut(
        id=question.id,
        topic_id=question.topic_id,
        text=question.text,
        answer=question.answer,
        cost=question.cost,
        is_visible=question.is_visible,
        topic_title=topic.title,
    )


@router.put("/{question_id}", response_model=web.api.schemas.QuestionOut)
async def update_question(
    question_id: uuid.UUID,
    body: web.api.schemas.QuestionUpdate,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> web.api.schemas.QuestionOut:
    question = await session.get(game.models.QuestionModel, question_id)
    if not question:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_QUESTION_NOT_FOUND,
        )

    if body.topic_id is not None:
        topic = await session.get(game.models.TopicModel, body.topic_id)
        if not topic:
            raise fastapi.HTTPException(
                status_code=404,
                detail=game.constants.API_MSG_TOPIC_NOT_FOUND,
            )
        question.topic_id = body.topic_id

    if body.text is not None:
        question.text = body.text
    if body.answer is not None:
        question.answer = body.answer
    if body.cost is not None:
        question.cost = body.cost

    await session.commit()
    await session.refresh(question)

    topic = await session.get(game.models.TopicModel, question.topic_id)
    return web.api.schemas.QuestionOut(
        id=question.id,
        topic_id=question.topic_id,
        text=question.text,
        answer=question.answer,
        cost=question.cost,
        is_visible=question.is_visible,
        topic_title=topic.title if topic else None,
    )


@router.delete("/{question_id}")
async def delete_question(
    question_id: uuid.UUID,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> fastapi.Response:
    question = await session.get(game.models.QuestionModel, question_id)
    if not question:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_QUESTION_NOT_FOUND,
        )

    qig_ids = [
        row[0]
        for row in (
            await session.execute(
                sqlalchemy.select(game.models.QuestionInGameModel.id).where(
                    game.models.QuestionInGameModel.question_id == question_id,
                )
            )
        ).all()
    ]
    if qig_ids:
        await session.execute(
            sqlalchemy.delete(game.models.GameItemUsageModel).where(
                game.models.GameItemUsageModel.question_in_game_id.in_(qig_ids),
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
                game.models.QuestionInGameModel.question_id == question_id,
            )
        )

    await session.execute(
        sqlalchemy.delete(game.models.QuestionModel).where(
            game.models.QuestionModel.id == question_id,
        )
    )
    await session.commit()
    return fastapi.Response(status_code=204)


@router.post("/bulk", response_model=web.api.schemas.BulkImportResult)
async def bulk_import_csv(
    file: fastapi.UploadFile,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> web.api.schemas.BulkImportResult:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    required = {"topic", "question", "answer", "cost"}
    if not reader.fieldnames or not required.issubset(
        {f.strip().lower() for f in reader.fieldnames}
    ):
        raise fastapi.HTTPException(
            status_code=400,
            detail=game.constants.API_MSG_CSV_COLUMNS.format(
                ", ".join(sorted(required))
            ),
        )

    field_map = {f.strip().lower(): f for f in reader.fieldnames}

    topic_cache: dict[str, uuid.UUID] = {}
    created = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        topic_title = row[field_map["topic"]].strip()
        question_text = row[field_map["question"]].strip()
        answer_text = row[field_map["answer"]].strip()
        cost_raw = row[field_map["cost"]].strip()

        if not all([topic_title, question_text, answer_text, cost_raw]):
            errors.append(f"Row {i}: empty required field")
            continue

        try:
            cost = int(cost_raw)
            if cost <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"Row {i}: cost must be a positive integer")
            continue

        if topic_title not in topic_cache:
            existing = (
                await session.execute(
                    sqlalchemy.select(game.models.TopicModel).where(
                        game.models.TopicModel.title == topic_title,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                topic_cache[topic_title] = existing.id
            else:
                new_topic = game.models.TopicModel(title=topic_title)
                session.add(new_topic)
                await session.flush()
                topic_cache[topic_title] = new_topic.id

        question = game.models.QuestionModel(
            topic_id=topic_cache[topic_title],
            text=question_text,
            answer=answer_text,
            cost=cost,
        )
        session.add(question)
        created += 1

    await session.commit()
    return web.api.schemas.BulkImportResult(created=created, errors=errors)
