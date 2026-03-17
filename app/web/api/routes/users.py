from __future__ import annotations

import typing

import fastapi
import game.constants
import game.models
import sqlalchemy
import sqlalchemy.ext.asyncio
import web.api.dependencies
import web.api.schemas

router = fastapi.APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[web.api.schemas.UserOut])
async def list_users(
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> list[web.api.schemas.UserOut]:
    stmt = sqlalchemy.select(game.models.UserModel).order_by(
        sqlalchemy.desc(game.models.UserModel.created_at),
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [web.api.schemas.UserOut.model_validate(u) for u in rows]


@router.get("/{user_id}", response_model=web.api.schemas.UserOut)
async def get_user(
    user_id: int,
    session: typing.Annotated[
        sqlalchemy.ext.asyncio.AsyncSession,
        fastapi.Depends(web.api.dependencies.get_session),
    ],
    _admin: typing.Annotated[
        str, fastapi.Depends(web.api.dependencies.require_admin)
    ],
) -> web.api.schemas.UserOut:
    user = await session.get(game.models.UserModel, user_id)
    if not user:
        raise fastapi.HTTPException(
            status_code=404,
            detail=game.constants.API_MSG_USER_NOT_FOUND,
        )
    return web.api.schemas.UserOut.model_validate(user)
