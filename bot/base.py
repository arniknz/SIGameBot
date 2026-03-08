import asyncio
import logging

import bot.poller
import bot.worker
import clients.schemas
import clients.tg

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, token: str, concurrent_workers: int = 3):
        self._tg = clients.tg.TgClient(token)
        self._queue: asyncio.Queue[clients.schemas.Update] = asyncio.Queue()
        self._poller = bot.poller.Poller(self._tg, self._queue)
        self._workers = [
            bot.worker.Worker(self._tg, self._queue, worker_id=i)
            for i in range(concurrent_workers)
        ]

    async def start(self) -> None:
        logger.info(
            'Bot starting with %d workers', len(self._workers),
        )
        await self._poller.start()
        for worker in self._workers:
            await worker.start()

    async def stop(self) -> None:
        logger.info('Bot shutting down')
        await self._poller.stop()
        for worker in self._workers:
            await worker.stop()
        await self._tg.close()
        logger.info('Bot stopped')
