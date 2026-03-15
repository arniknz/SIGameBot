from __future__ import annotations

import asyncio
import logging

import aiohttp
import clients.rabbitmq
import clients.tg

logger = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        tg_client: clients.tg.TgClient,
        rabbitmq: clients.rabbitmq.RabbitMQClient,
    ):
        self._tg = tg_client
        self._rabbitmq = rabbitmq
        self._offset: int | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def _poll(self) -> None:
        while self._running:
            try:
                updates = await self._tg.get_updates(
                    offset=self._offset,
                    poll_timeout=30,
                )
                for update in updates:
                    self._offset = update.update_id + 1
                    await self._rabbitmq.publish_update(
                        update.model_dump()
                    )
                    logger.debug(
                        "Published update %d to RabbitMQ", update.update_id
                    )
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, OSError) as exc:
                logger.warning(
                    "Poller network error, retrying in 5s: %s",
                    exc,
                )
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Poller unexpected error, retrying in 5s")
                await asyncio.sleep(5)

    async def start(self) -> None:
        logger.info("Poller starting")
        self._running = True
        self._task = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        logger.info("Poller stopping")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
