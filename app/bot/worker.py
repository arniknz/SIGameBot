from __future__ import annotations

import asyncio
import logging

import bot.dispatcher
import clients.schemas

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        dispatcher: bot.dispatcher.Dispatcher,
        queue: asyncio.Queue[clients.schemas.Update],
        worker_id: int,
    ):
        self._dispatcher = dispatcher
        self._queue = queue
        self._id = worker_id
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
                continue
            except asyncio.CancelledError:
                break

            self._processing = True
            try:
                await self._dispatcher.handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker-%d error handling update", self._id)
            finally:
                self._processing = False
                self._queue.task_done()

        logger.info("Worker-%d loop exited", self._id)

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
                    "Worker-%d did not finish in time, cancelling",
                    self._id,
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        logger.info("Worker-%d stopped", self._id)
