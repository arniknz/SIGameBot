from __future__ import annotations

import typing

import fastapi
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
from web.api import dependencies, schemas

router = fastapi.APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[schemas.UserOut])
async def list_users(
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(dependencies.get_session),
    ],
    _admin: typing.Annotated[str, fastapi.Depends(dependencies.require_admin)],
) -> list[schemas.UserOut]:
    stmt = sqlalchemy.select(game.models.UserModel).order_by(
        sqlalchemy.desc(game.models.UserModel.created_at),
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [schemas.UserOut.model_validate(u) for u in rows]


@router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user(
    user_id: int,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(dependencies.get_session),
    ],
    _admin: typing.Annotated[str, fastapi.Depends(dependencies.require_admin)],
) -> schemas.UserOut:
    user = await session.get(game.models.UserModel, user_id)
    if not user:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    return schemas.UserOut.model_validate(user)
