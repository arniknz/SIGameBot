from __future__ import annotations

import contextlib
import logging
import typing

import config
import fastapi
import nlp.openrouter
import web.api.dependencies
import web.api.routes.games
import web.api.routes.questions
import web.api.routes.topics
import web.api.routes.users
import web.api.schemas

logger = logging.getLogger(__name__)


def _get_config() -> config.Config:
    return config.Config.from_env()


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> typing.AsyncIterator[None]:
    cfg = _get_config()
    web.api.dependencies.init_auth(cfg)
    await web.api.dependencies.init_db(cfg)
    if not cfg.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY must be set in environment")
    nlp.openrouter.set_openrouter_client(
        nlp.openrouter.OpenRouterClient(
            api_key=cfg.openrouter_api_key,
            model=cfg.openrouter_model,
        )
    )
    logger.info("Admin API started on port %s", cfg.admin_api_port)

    yield

    await web.api.dependencies.close_db()
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
api_router.include_router(web.api.routes.topics.router)
api_router.include_router(web.api.routes.questions.router)
api_router.include_router(web.api.routes.users.router)
api_router.include_router(web.api.routes.games.router)


@api_router.get(
    "/config", response_model=web.api.schemas.ConfigOut, tags=["Config"]
)
async def get_config(
    _admin: typing.Annotated[
        str,
        fastapi.Depends(web.api.dependencies.require_admin),
    ],
) -> web.api.schemas.ConfigOut:
    cfg = _get_config()
    return web.api.schemas.ConfigOut(
        question_selection_timeout=cfg.question_selection_timeout,
        buzzer_timeout=cfg.buzzer_timeout,
        answer_timeout=cfg.answer_timeout,
        max_failed_selections=cfg.max_failed_selections,
    )


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "SIGameBot Admin API",
        "docs": "/docs",
    }
