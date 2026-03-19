from __future__ import annotations

import asyncio
import logging

import aiohttp
import bot.dialog
import bot.dispatcher
import bot.handlers
import bot.poller
import bot.views
import bot.worker
import clients.rabbitmq
import clients.tg
import config
import db.database
import game.schemas
import game.services

logger = logging.getLogger(__name__)

TIMER_HEARTBEAT_SECONDS = 5


class Bot:
    def __init__(self, cfg: config.Config):
        self._config = cfg
        self._tg = clients.tg.TgClient(cfg.bot_token)
        self._db = db.database.Database(cfg)
        self._rabbitmq = clients.rabbitmq.RabbitMQClient(cfg.rabbitmq_url)

        session_factory = self._db.session_factory

        self._lobby = game.services.LobbyService(
            session_factory,
            question_selection_timeout=cfg.question_selection_timeout,
        )
        self._gameplay = game.services.GameplayService(
            session_factory,
            question_selection_timeout=cfg.question_selection_timeout,
            buzzer_timeout=cfg.buzzer_timeout,
            answer_timeout=cfg.answer_timeout,
            answer_similarity_threshold=cfg.answer_similarity_threshold,
            answer_fuzzy_ratio_min=cfg.answer_fuzzy_ratio_min,
            sentence_transformer_model=cfg.sentence_transformer_model,
            max_question_word_overlap=cfg.max_question_word_overlap,
            max_question_similarity=cfg.max_question_similarity,
            min_answer_similarity=cfg.min_answer_similarity,
            enable_phonetic=cfg.enable_phonetic,
            phonetic_threshold=cfg.phonetic_threshold,
        )
        self._content = game.services.ContentService(
            session_factory,
            buzzer_timeout=cfg.buzzer_timeout,
            answer_timeout=cfg.answer_timeout,
            sentence_transformer_model=cfg.sentence_transformer_model,
            max_csv_rows=cfg.max_csv_rows,
        )
        self._timer = game.services.TimerService(
            session_factory,
            question_selection_timeout=cfg.question_selection_timeout,
            max_failed_selections=cfg.max_failed_selections,
            lobby_timeout=cfg.lobby_timeout,
        )
        self._shop = game.services.ShopService(session_factory)
        self._dialog = bot.dialog.DialogManager()

        router = bot.handlers.create_router(
            lobby=self._lobby,
            gameplay=self._gameplay,
            content=self._content,
            dialog=self._dialog,
            shop=self._shop,
        )
        self._dispatcher = bot.dispatcher.Dispatcher(
            tg=self._tg,
            router=router,
            dialog_manager=self._dialog,
            content_service=self._content,
            gameplay_service=self._gameplay,
            lobby_service=self._lobby,
        )
        self._poller = bot.poller.Poller(self._tg, self._rabbitmq)

        timer_delays_ms = [
            (cfg.buzzer_timeout + 1) * 1000,
            (cfg.answer_timeout + 1) * 1000,
            (cfg.question_selection_timeout + 1) * 1000,
        ]
        self._workers = [
            bot.worker.Worker(
                dispatcher=self._dispatcher,
                rabbitmq=self._rabbitmq,
                worker_id=i,
                timer_delays_ms=timer_delays_ms,
            )
            for i in range(cfg.workers_count)
        ]
        self._timer_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

    async def start(self) -> None:
        logger.info("Bot starting with %d workers", len(self._workers))
        await self._db.connect()
        await self._rabbitmq.connect()
        await self._tg.start()
        await self._poller.start()
        for worker in self._workers:
            await worker.start()
        self._timer_task = asyncio.create_task(self._timer_consumer())
        self._heartbeat_task = asyncio.create_task(self._timer_heartbeat())
        await self._rabbitmq.publish_timer_check(delay_ms=0)
        logger.info("Bot is ready")

    async def _timer_consumer(self) -> None:
        queue = await self._rabbitmq.create_consumer(
            clients.rabbitmq.TIMER_EVENTS_QUEUE,
            prefetch_count=1,
        )
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    await message.ack()
                    service_responses = await self._timer.check_timers()
                    responses = bot.views.render_many(service_responses)
                    await self._send_responses(responses)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Timer consumer error")

    async def _timer_heartbeat(self) -> None:
        while True:
            try:
                await asyncio.sleep(TIMER_HEARTBEAT_SECONDS)
                await self._rabbitmq.publish_timer_check(delay_ms=0)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timer heartbeat error")
                await asyncio.sleep(TIMER_HEARTBEAT_SECONDS)

    async def _send_responses(
        self,
        responses: list[game.schemas.GameResponse],
    ) -> None:
        tasks = []
        for response in responses:
            if response.edit_message_id:
                tasks.append(
                    self._tg.edit_message_text(
                        response.chat_id,
                        response.edit_message_id,
                        response.text,
                        buttons=response.keyboard,
                    )
                )
            elif response.keyboard:
                tasks.append(
                    self._tg.send_keyboard(
                        response.chat_id,
                        response.text,
                        response.keyboard,
                    )
                )
            else:
                tasks.append(
                    self._tg.send_message(
                        response.chat_id,
                        response.text,
                    )
                )
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    if isinstance(result, (aiohttp.ClientError, OSError)):
                        logger.warning(
                            "Timer network error for chat %d: %s",
                            responses[idx].chat_id,
                            result,
                        )
                    else:
                        logger.error(
                            "Timer send error for chat %d: %s",
                            responses[idx].chat_id,
                            result,
                            exc_info=result,
                        )

    async def stop(self) -> None:
        logger.info("Bot shutting down gracefully...")

        logger.info("Stopping poller (no new updates)")
        await self._poller.stop()

        if self._heartbeat_task:
            logger.info("Cancelling timer heartbeat")
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._timer_task:
            logger.info("Cancelling timer consumer")
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopping %d workers...", len(self._workers))
        await asyncio.gather(*(worker.stop() for worker in self._workers))
        logger.info("All workers stopped")

        logger.info("Closing Telegram client")
        await self._tg.close()

        logger.info("Closing RabbitMQ connections")
        try:
            await self._rabbitmq.close()
        except Exception:
            logger.warning("Error closing RabbitMQ", exc_info=True)

        logger.info("Closing database connections")
        try:
            await self._db.disconnect()
        except Exception:
            logger.warning("Error closing database", exc_info=True)

        logger.info("Bot stopped cleanly")
