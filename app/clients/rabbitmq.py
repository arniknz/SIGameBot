from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
import aio_pika.abc
import aio_pika.pool

logger = logging.getLogger(__name__)

UPDATES_QUEUE = "game_updates"
TIMER_DELAY_QUEUE = "timer_delay"
TIMER_EVENTS_QUEUE = "timer_events"
TIMER_DLX_EXCHANGE = "timer_dlx"

CONNECT_RETRIES = 10
CONNECT_RETRY_DELAY = 3


class RabbitMQClient:
    def __init__(
        self,
        url: str,
        connection_pool_size: int = 2,
        channel_pool_size: int = 10,
    ) -> None:
        self._url = url
        self._connection_pool_size = connection_pool_size
        self._channel_pool_size = channel_pool_size
        self._connection_pool: aio_pika.pool.Pool | None = None
        self._channel_pool: aio_pika.pool.Pool | None = None
        self._consumer_connections: list[
            aio_pika.abc.AbstractRobustConnection
        ] = []

    async def _create_connection(self) -> aio_pika.abc.AbstractRobustConnection:
        return await aio_pika.connect_robust(self._url)

    def _get_connection_pool(self) -> aio_pika.pool.Pool:
        if self._connection_pool is None:
            raise RuntimeError("RabbitMQ not connected; call connect() first")
        return self._connection_pool

    def _get_channel_pool(self) -> aio_pika.pool.Pool:
        if self._channel_pool is None:
            raise RuntimeError("RabbitMQ not connected; call connect() first")
        return self._channel_pool

    async def _create_channel(self) -> aio_pika.abc.AbstractRobustChannel:
        async with self._get_connection_pool().acquire() as connection:
            return await connection.channel()

    async def connect(self) -> None:
        safe_url = self._url.split("@")[-1] if "@" in self._url else self._url
        logger.info("Connecting to RabbitMQ at %s", safe_url)

        last_exc: Exception | None = None
        for attempt in range(1, CONNECT_RETRIES + 1):
            try:
                self._connection_pool = aio_pika.pool.Pool(
                    self._create_connection,
                    max_size=self._connection_pool_size,
                )
                self._channel_pool = aio_pika.pool.Pool(
                    self._create_channel,
                    max_size=self._channel_pool_size,
                )
                await self._declare_infrastructure()
                logger.info("RabbitMQ connected, infrastructure declared")
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "RabbitMQ connect attempt %d/%d failed: %s",
                    attempt,
                    CONNECT_RETRIES,
                    exc,
                )
                if attempt < CONNECT_RETRIES:
                    await asyncio.sleep(CONNECT_RETRY_DELAY)

        raise ConnectionError(
            f"Failed to connect to RabbitMQ after {CONNECT_RETRIES} attempts"
        ) from last_exc

    async def _declare_infrastructure(self) -> None:
        async with self._get_channel_pool().acquire() as channel:
            await channel.declare_queue(UPDATES_QUEUE, durable=True)

            timer_dlx = await channel.declare_exchange(
                TIMER_DLX_EXCHANGE,
                aio_pika.ExchangeType.FANOUT,
                durable=True,
            )
            timer_events = await channel.declare_queue(
                TIMER_EVENTS_QUEUE,
                durable=True,
            )
            await timer_events.bind(timer_dlx)

            await channel.declare_queue(
                TIMER_DELAY_QUEUE,
                durable=True,
                arguments={"x-dead-letter-exchange": TIMER_DLX_EXCHANGE},
            )

    async def publish_update(self, update_data: dict) -> None:
        async with self._get_channel_pool().acquire() as channel:
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(update_data).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=UPDATES_QUEUE,
            )

    async def publish_timer_check(self, delay_ms: int = 0) -> None:
        body = b'{"type":"timer_check"}'
        async with self._get_channel_pool().acquire() as channel:
            if delay_ms <= 0:
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=body,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    ),
                    routing_key=TIMER_EVENTS_QUEUE,
                )
            else:
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=body,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        expiration=delay_ms,
                    ),
                    routing_key=TIMER_DELAY_QUEUE,
                )

    async def create_consumer(
        self,
        queue_name: str,
        prefetch_count: int = 1,
    ) -> aio_pika.abc.AbstractQueue:
        connection = await aio_pika.connect_robust(self._url)
        self._consumer_connections.append(connection)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=prefetch_count)
        return await channel.declare_queue(queue_name, durable=True)

    async def close(self) -> None:
        logger.info("Closing RabbitMQ connections")
        for conn in self._consumer_connections:
            try:
                await conn.close()
            except Exception:
                logger.debug("Error closing consumer connection", exc_info=True)
        self._consumer_connections.clear()

        if self._channel_pool:
            await self._channel_pool.close()
        if self._connection_pool:
            await self._connection_pool.close()
        logger.info("RabbitMQ connections closed")
