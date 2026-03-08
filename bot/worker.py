import asyncio
import logging

import clients.schemas
import clients.tg

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        tg_client: clients.tg.TgClient,
        queue: asyncio.Queue[clients.schemas.Update],
        worker_id: int,
    ):
        self._tg = tg_client
        self._queue = queue
        self._id = worker_id
        self._running = False
        self._task: asyncio.Task | None = None

    async def _handle_update(self, update: clients.schemas.Update) -> None:
        if update.message and update.message.text:
            chat_id = update.message.chat.id
            text = update.message.text
            username = ''
            if update.message.from_user:
                username = update.message.from_user.first_name
            logger.info(
                'Worker-%d: message from %s: %s',
                self._id,
                username,
                text,
            )
            await self._tg.send_message(chat_id, f'Echo: {text}')

        elif update.callback_query:
            cb = update.callback_query
            await self._tg.answer_callback(cb.id, text=f'Got: {cb.data}')
            if cb.message:
                await self._tg.send_message(
                    cb.message.chat.id,
                    f'Callback: {cb.data}',
                )

    async def _run(self) -> None:
        logger.info('Worker-%d started', self._id)
        while self._running:
            try:
                update = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            try:
                await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Worker-%d error handling update', self._id)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        logger.info('Worker-%d stopping', self._id)
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
