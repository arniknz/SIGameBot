from __future__ import annotations

import asyncio
import logging

import bot.handlers
import clients.schemas
import clients.tg
import game.logic
import game.schemas

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        handlers: bot.handlers.Handlers,
        queue: asyncio.Queue[clients.schemas.Update],
        worker_id: int,
        tg: clients.tg.TgClient,
        logic: game.logic.GameLogic,
    ):
        self._handlers = handlers
        self._queue = queue
        self._id = worker_id
        self._tg = tg
        self._logic = logic
        self._running = False
        self._processing = False
        self._task: asyncio.Task | None = None

    @property
    def is_idle(self) -> bool:
        return not self._processing

    async def _run(self) -> None:
        logger.info("Worker-%d started", self._id)
        while self._running:
            try:
                update = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                await self._check_timers()
                continue
            except asyncio.CancelledError:
                break

            self._processing = True
            try:
                await self._handlers.handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker-%d error handling update", self._id)
            finally:
                self._processing = False

        logger.info("Worker-%d loop exited", self._id)

    async def _check_timers(self) -> None:
        try:
            responses = await self._logic.check_timers()
        except Exception:
            logger.exception("Worker-%d error checking timers", self._id)
            return
        await self._send_timer_responses(responses)

    async def _send_timer_responses(
        self, responses: list[game.schemas.GameResponse]
    ) -> None:
        for resp in responses:
            try:
                if resp.keyboard:
                    await self._tg.send_keyboard(
                        resp.chat_id, resp.text, resp.keyboard
                    )
                else:
                    await self._tg.send_message(resp.chat_id, resp.text)
            except Exception:
                logger.exception(
                    "Worker-%d error sending timer response", self._id
                )

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        logger.info("Worker-%d stopping", self._id)
        self._running = False
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                logger.warning(
                    "Worker-%d did not finish in time, cancelling", self._id
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        logger.info("Worker-%d stopped", self._id)
