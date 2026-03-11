from __future__ import annotations

import logging
import asyncio

import bot.dialog
import bot.router
import bot.views
import clients.schemas
import clients.tg
import game.constants
import game.schemas
import game.services

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(
        self,
        tg: clients.tg.TgClient,
        router: bot.router.Router,
        dialog_manager: bot.dialog.DialogManager,
        content_service: game.services.ContentService,
        gameplay_service: game.services.GameplayService,
    ) -> None:
        self._tg = tg
        self._router = router
        self._dialog = dialog_manager
        self._content = content_service
        self._gameplay = gameplay_service

    async def handle_update(self, update: clients.schemas.Update) -> None:
        try:
            if update.message and update.message.text:
                await self._handle_message(update)
            elif update.callback_query:
                await self._handle_callback(update)
        except Exception:
            logger.exception("DB / handler error")
            chat_id = self._extract_chat_id(update)
            if chat_id:
                try:
                    await self._tg.send_message(
                        chat_id, game.constants.BotMessage.DB_ERROR
                    )
                except Exception:
                    logger.exception("Failed to send error message")

    @staticmethod
    def _extract_chat_id(update: clients.schemas.Update) -> int | None:
        if update.message:
            return update.message.chat.id
        if update.callback_query and update.callback_query.message:
            return update.callback_query.message.chat.id
        return None

    async def _handle_message(self, update: clients.schemas.Update) -> None:
        msg = update.message
        if not msg or not msg.text:
            return

        chat_id = msg.chat.id
        text = msg.text.strip()
        user = msg.from_user
        telegram_id = user.id if user else 0
        username = user.first_name if user else "Unknown"
        is_private = msg.chat.type == "private"

        if is_private and self._dialog.has_active(telegram_id):
            responses = await self._handle_dialog_input(
                telegram_id, chat_id, text
            )
            await self._send_responses(responses)
            return

        command, _, args = text.partition(" ")
        command = self._strip_mention(command).lower()

        if command.startswith("/"):
            cmd = command[1:]
            responses = await self._router.dispatch_command(
                cmd,
                private=is_private,
                chat_id=chat_id,
                telegram_id=telegram_id,
                username=username,
                args=args.strip(),
            )
            await self._send_responses(responses)
            return

        if not is_private:
            responses = await self._gameplay.handle_possible_answer(
                chat_id, telegram_id, username, text
            )
            if responses:
                await self._send_responses(bot.views.render_many(responses))

    @staticmethod
    def _strip_mention(command: str) -> str:
        at_pos = command.find("@")
        if at_pos != -1:
            return command[:at_pos]
        return command

    async def _handle_callback(self, update: clients.schemas.Update) -> None:
        cb = update.callback_query
        if not cb:
            return
        await self._tg.answer_callback(cb.id)

        data = cb.data or ""
        chat_id = cb.message.chat.id if cb.message else 0
        telegram_id = cb.from_user.id
        username = cb.from_user.first_name
        if not chat_id:
            return

        responses = await self._router.dispatch_callback(
            data,
            chat_id=chat_id,
            telegram_id=telegram_id,
            username=username,
        )
        await self._send_responses(responses)

    async def _handle_dialog_input(
        self,
        telegram_id: int,
        chat_id: int,
        text: str,
    ) -> list[game.schemas.GameResponse]:
        if text.startswith("/"):
            cmd = self._strip_mention(text.split(maxsplit=1)[0]).lower()
            if cmd in ("/cancel", "/done"):
                self._dialog.clear(telegram_id)
                return bot.views.render_many(
                    [game.schemas.ServiceResponse(chat_id, "dialog_cancelled")]
                )

        state = self._dialog.get(telegram_id)
        if not state:
            return []

        step = state.step
        prompt: str | None = None

        if step == game.constants.DialogStep.AWAIT_TOPIC_NAME:
            return await self._dialog_topic_name(telegram_id, chat_id, text)

        if step == game.constants.DialogStep.AWAIT_QUESTION_TEXT:
            state.question_text = text
            self._dialog.advance(
                telegram_id, game.constants.DialogStep.AWAIT_QUESTION_ANSWER
            )
            prompt = "Now send the correct answer:"

        elif step == game.constants.DialogStep.AWAIT_QUESTION_ANSWER:
            state.question_answer = text
            self._dialog.advance(
                telegram_id, game.constants.DialogStep.AWAIT_QUESTION_COST
            )
            prompt = "Enter the point cost (e.g. 100, 200, 500):"

        elif step == game.constants.DialogStep.AWAIT_QUESTION_COST:
            return await self._dialog_question_cost(
                telegram_id, chat_id, text, state
            )

        else:
            self._dialog.clear(telegram_id)
            return []

        return [game.schemas.GameResponse(chat_id=chat_id, text=prompt)]

    async def _dialog_topic_name(
        self,
        telegram_id: int,
        chat_id: int,
        text: str,
    ) -> list[game.schemas.GameResponse]:
        topic_name = text.strip()
        if not topic_name:
            return [
                game.schemas.GameResponse(
                    chat_id=chat_id,
                    text="Topic name cannot be empty. Try again:",
                )
            ]
        responses = await self._content.handle_add_topic(
            chat_id, telegram_id, topic_name
        )
        self._dialog.clear(telegram_id)
        return bot.views.render_many(responses)

    async def _dialog_question_cost(
        self,
        telegram_id: int,
        chat_id: int,
        text: str,
        state: game.schemas.DialogState,
    ) -> list[game.schemas.GameResponse]:
        try:
            cost = int(text.strip())
        except ValueError:
            return [
                game.schemas.GameResponse(
                    chat_id=chat_id, text="Must be a number. Try again:"
                )
            ]
        responses = await self._content.handle_add_question(
            chat_id,
            telegram_id,
            state.topic_id,
            state.question_text,
            state.question_answer,
            cost,
        )
        self._dialog.clear(telegram_id)
        return bot.views.render_many(responses)

    async def _send_responses(
        self, responses: list[game.schemas.GameResponse]
    ) -> None:
        tasks = []
        for resp in responses:
            if resp.keyboard:
                tasks.append(
                    self._tg.send_keyboard(resp.chat_id, resp.text, resp.keyboard)
                )
            else:
                tasks.append(self._tg.send_message(resp.chat_id, resp.text))
        if not tasks:
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception(
                    "Failed to send response to chat %d",
                    responses[idx].chat_id,
                    exc_info=result,
                )
