from __future__ import annotations

import asyncio
import json
import logging

import bot.dispatcher
import clients.rabbitmq
import clients.schemas
import game.constants

logger = logging.getLogger(__name__)


GAME_COMMANDS_PREFETCH = 20


class Worker:
    def __init__(
        self,
        dispatcher: bot.dispatcher.Dispatcher,
        rabbitmq: clients.rabbitmq.RabbitMQClient,
        worker_id: int,
        timer_delays_ms: list[int],
        prefetch_count: int = GAME_COMMANDS_PREFETCH,
    ):
        self._dispatcher = dispatcher
        self._rabbitmq = rabbitmq
        self._id = worker_id
        self._timer_delays_ms = timer_delays_ms
        self._prefetch_count = prefetch_count
        self._running = False
        self._processing = False
        self._task: asyncio.Task | None = None

    @property
    def is_idle(self) -> bool:
        return not self._processing

    async def _run(self) -> None:
        logger.info("Worker-%d started", self._id)
        queue = await self._rabbitmq.create_consumer(
            clients.rabbitmq.UPDATES_QUEUE,
            prefetch_count=self._prefetch_count,
        )
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                self._processing = True
                try:
                    data = json.loads(message.body)
                    update = clients.schemas.Update.model_validate(data)
                    await self._dispatcher.handle_update(update)
                    await self._schedule_timer_checks(update)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Worker-%d error handling update", self._id
                    )
                finally:
                    self._processing = False
                    try:
                        await message.ack()
                    except (OSError, RuntimeError) as exc:
                        logger.debug("Message ack failed: %s", exc)

        logger.info("Worker-%d loop exited", self._id)

    async def _schedule_timer_checks(
        self, update: clients.schemas.Update
    ) -> None:
        is_group = (
            update.message is not None
            and update.message.chat.type != game.constants.ChatType.PRIVATE
        ) or update.callback_query is not None

        if not is_group:
            return

        for delay_ms in self._timer_delays_ms:
            try:
                await self._rabbitmq.publish_timer_check(delay_ms=delay_ms)
            except Exception:
                logger.debug("Failed to schedule timer check", exc_info=True)

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
