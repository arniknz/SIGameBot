from __future__ import annotations

import contextlib
import logging
import typing

import config
import fastapi
from web.api import dependencies, schemas
from web.api.routes import games, questions, topics, users

logger = logging.getLogger(__name__)


def _get_config() -> config.Config:
    return config.Config.from_env()


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> typing.AsyncIterator[None]:
    cfg = _get_config()
    dependencies.init_auth(cfg)
    await dependencies.init_db(cfg)
    logger.info("Admin API started on port %s", cfg.admin_api_port)

    yield

    await dependencies.close_db()
    logger.info("Admin API stopped")


app = fastapi.FastAPI(
    title="SIGameBot Admin API",
    description="Admin panel for managing Jeopardy bot content and monitoring",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

api_router = fastapi.APIRouter(prefix="/api")
api_router.include_router(topics.router)
api_router.include_router(questions.router)
api_router.include_router(users.router)
api_router.include_router(games.router)


@api_router.get("/config", response_model=schemas.ConfigOut, tags=["Config"])
async def get_config(
    _admin: typing.Annotated[
        str,
        fastapi.Depends(dependencies.require_admin),
    ],
) -> schemas.ConfigOut:
    cfg = _get_config()
    return schemas.ConfigOut(
        question_selection_timeout=cfg.question_selection_timeout,
        buzzer_timeout=cfg.buzzer_timeout,
        answer_timeout=cfg.answer_timeout,
    )


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "SIGameBot Admin API",
        "docs": "/docs",
    }
