from __future__ import annotations

import secrets
import typing

import config
import db.database
import fastapi
import fastapi.security
import sqlalchemy.ext.asyncio

_security = fastapi.security.HTTPBasic()

_cfg: config.Config | None = None
_db: db.database.Database | None = None


def init_auth(cfg: config.Config) -> None:
    global _cfg
    _cfg = cfg


async def init_db(cfg: config.Config) -> None:
    global _db
    _db = db.database.Database(cfg)
    await _db.connect()


async def close_db() -> None:
    if _db is not None:
        await _db.disconnect()


async def get_session() -> typing.AsyncIterator[
    sqlalchemy.ext.asyncio.AsyncSession
]:
    if _db is None:
        raise RuntimeError("Database not initialized")
    async with _db.session_factory() as session:
        yield session


def require_admin(
    credentials: typing.Annotated[
        fastapi.security.HTTPBasicCredentials,
        fastapi.Depends(_security),
    ],
) -> str:
    if _cfg is None:
        raise fastapi.HTTPException(
            status_code=500,
            detail="Server misconfigured",
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode(),
        _cfg.admin_username.encode(),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode(),
        _cfg.admin_password.encode(),
    )
    if not (username_ok and password_ok):
        raise fastapi.HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
