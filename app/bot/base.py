from __future__ import annotations

import asyncio
import logging

import bot.dialog
import bot.handlers
import bot.poller
import bot.worker
import clients.schemas
import clients.tg
import config
import db.database
import game.logic

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, cfg: config.Config):
        self._config = cfg
        self._tg = clients.tg.TgClient(cfg.bot_token)
        self._db = db.database.Database(cfg)
        self._queue: asyncio.Queue[clients.schemas.Update] = asyncio.Queue()

        self._logic = game.logic.GameLogic(
            session_factory=self._db.session_factory,
            buzzer_timeout=cfg.buzzer_timeout,
            answer_timeout=cfg.answer_timeout,
        )
        self._dialog = bot.dialog.DialogManager()
        self._handlers = bot.handlers.Handlers(
            self._tg, self._logic, self._dialog
        )
        self._poller = bot.poller.Poller(self._tg, self._queue)
        self._workers = [
            bot.worker.Worker(
                handlers=self._handlers,
                queue=self._queue,
                worker_id=i,
                tg=self._tg,
                logic=self._logic,
            )
            for i in range(cfg.workers_count)
        ]

    async def start(self) -> None:
        logger.info("Bot starting with %d workers", len(self._workers))
        await self._db.connect()
        await self._poller.start()
        for worker in self._workers:
            await worker.start()
        logger.info("Bot is ready")

    async def stop(self) -> None:
        logger.info("Bot shutting down")
        await self._poller.stop()
        for worker in self._workers:
            await worker.stop()
        await self._tg.close()
        try:
            await self._db.disconnect()
        except Exception:
            logger.warning("Error closing database", exc_info=True)
        logger.info("Bot stopped")
