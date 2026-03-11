from __future__ import annotations

import asyncio
import logging

import bot.dialog
import bot.dispatcher
import bot.handlers
import bot.poller
import bot.views
import bot.worker
import clients.schemas
import clients.tg
import config
import db.database
import game.services

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, cfg: config.Config):
        self._config = cfg
        self._tg = clients.tg.TgClient(cfg.bot_token)
        self._db = db.database.Database(cfg)
        self._queue: asyncio.Queue[clients.schemas.Update] = asyncio.Queue()

        session_factory = self._db.session_factory

        self._lobby = game.services.LobbyService(session_factory)
        self._gameplay = game.services.GameplayService(
            session_factory,
            buzzer_timeout=cfg.buzzer_timeout,
            answer_timeout=cfg.answer_timeout,
        )
        self._content = game.services.ContentService(
            session_factory,
            buzzer_timeout=cfg.buzzer_timeout,
            answer_timeout=cfg.answer_timeout,
        )
        self._timer = game.services.TimerService(session_factory)
        self._dialog = bot.dialog.DialogManager()

        router = bot.handlers.create_router(
            lobby=self._lobby,
            gameplay=self._gameplay,
            content=self._content,
            dialog=self._dialog,
        )
        self._dispatcher = bot.dispatcher.Dispatcher(
            tg=self._tg,
            router=router,
            dialog_manager=self._dialog,
            content_service=self._content,
            gameplay_service=self._gameplay,
        )
        self._poller = bot.poller.Poller(self._tg, self._queue)
        self._workers = [
            bot.worker.Worker(
                dispatcher=self._dispatcher,
                queue=self._queue,
                worker_id=i,
            )
            for i in range(cfg.workers_count)
        ]
        self._timer_task: asyncio.Task | None = None

    async def start(self) -> None:
        logger.info("Bot starting with %d workers", len(self._workers))
        await self._db.connect()
        await self._tg.start()
        await self._poller.start()
        for worker in self._workers:
            await worker.start()
        self._timer_task = asyncio.create_task(self._timer_loop())
        logger.info("Bot is ready")

    async def _timer_loop(self) -> None:
        while True:
            try:
                service_responses = await self._timer.check_timers()
                responses = bot.views.render_many(service_responses)
                send_tasks = []
                for response in responses:
                    if response.keyboard:
                        send_tasks.append(
                            self._tg.send_keyboard(
                                response.chat_id,
                                response.text,
                                response.keyboard,
                            )
                        )
                    else:
                        send_tasks.append(
                            self._tg.send_message(
                                response.chat_id,
                                response.text,
                            )
                        )
                if send_tasks:
                    await asyncio.gather(*send_tasks)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timer loop error")
            await asyncio.sleep(1)

    async def stop(self) -> None:
        logger.info("Bot shutting down")
        await self._poller.stop()
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass

        try:
            await asyncio.wait_for(self._queue.join(), timeout=10)
        except TimeoutError:
            logger.warning("Queue drain timed out; forcing worker stop")

        await asyncio.gather(*(worker.stop() for worker in self._workers))
        await self._tg.close()
        try:
            await self._db.disconnect()
        except Exception:
            logger.warning("Error closing database", exc_info=True)
        logger.info("Bot stopped")
