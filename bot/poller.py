from __future__ import annotations

import asyncio
import logging

import clients.schemas
import clients.tg

logger = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        tg_client: clients.tg.TgClient,
        queue: asyncio.Queue[clients.schemas.Update],
    ):
        self._tg = tg_client
        self._queue = queue
        self._offset: int | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def _poll(self) -> None:
        while self._running:
            try:
                updates = await self._tg.get_updates(
                    offset=self._offset,
                    timeout=30,
                )
                for update in updates:
                    self._offset = update.update_id + 1
                    await self._queue.put(update)
                    logger.debug('Queued update %d', update.update_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Poller error, retrying in 5s')
                await asyncio.sleep(5)

    async def start(self) -> None:
        logger.info('Poller starting')
        self._running = True
        self._task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        logger.info('Poller stopping')
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
