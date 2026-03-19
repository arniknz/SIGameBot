from __future__ import annotations

import secrets
import typing

import config
import db.database
import fastapi
import fastapi.security
import game.constants
import sqlalchemy.ext.asyncio

_security = fastapi.security.HTTPBasic()


class _AppState:
    cfg: config.Config | None = None
    db: db.database.Database | None = None


_state = _AppState()


def init_auth(cfg: config.Config) -> None:
    _state.cfg = cfg


async def init_db(cfg: config.Config) -> None:
    _state.db = db.database.Database(cfg)
    await _state.db.connect()


async def close_db() -> None:
    if _state.db is not None:
        await _state.db.disconnect()


async def get_session() -> typing.AsyncIterator[
    sqlalchemy.ext.asyncio.AsyncSession
]:
    if _state.db is None:
        raise RuntimeError("Database not initialized")
    async with _state.db.session_factory() as session:
        yield session


def get_config() -> config.Config:
    if _state.cfg is None:
        raise RuntimeError("Config not initialized")
    return _state.cfg


def require_admin(
    credentials: typing.Annotated[
        fastapi.security.HTTPBasicCredentials,
        fastapi.Depends(_security),
    ],
) -> str:
    if _state.cfg is None:
        raise fastapi.HTTPException(
            status_code=500,
            detail=game.constants.API_MSG_SERVER_MISCONFIGURED,
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode(),
        _state.cfg.admin_username.encode(),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode(),
        _state.cfg.admin_password.encode(),
    )
    if not (username_ok and password_ok):
        raise fastapi.HTTPException(
            status_code=401,
            detail=game.constants.API_MSG_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
