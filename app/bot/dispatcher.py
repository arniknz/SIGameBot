from __future__ import annotations

import asyncio
import logging

import aiohttp
import bot.dialog
import bot.router
import bot.views
import clients.schemas
import clients.tg
import game.constants
import game.schemas
import game.services
import sqlalchemy.exc

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(
        self,
        tg: clients.tg.TgClient,
        router: bot.router.Router,
        dialog_manager: bot.dialog.DialogManager,
        content_service: game.services.ContentService,
        gameplay_service: game.services.GameplayService,
        lobby_service: game.services.LobbyService | None = None,
    ) -> None:
        self._tg = tg
        self._router = router
        self._dialog = dialog_manager
        self._content = content_service
        self._gameplay = gameplay_service
        self._lobby = lobby_service

    async def handle_update(self, update: clients.schemas.Update) -> None:
        try:
            if update.message and update.message.document:
                await self._handle_document(update)
            elif update.message and update.message.text:
                await self._handle_message(update)
            elif update.callback_query:
                await self._handle_callback(update)
        except Exception:
            logger.exception("DB / handler error")
            chat_id = self._extract_chat_id(update)
            if chat_id:
                try:
                    await self._tg.send_message(
                        chat_id,
                        game.constants.BotMessage.DB_ERROR,
                    )
                except Exception:
                    logger.exception("Failed to send error message")

    @staticmethod
    def _extract_chat_id(
        update: clients.schemas.Update,
    ) -> int | None:
        if update.message:
            return update.message.chat.id
        if update.callback_query and update.callback_query.message:
            return update.callback_query.message.chat.id
        return None

    async def _handle_document(self, update: clients.schemas.Update) -> None:
        msg = update.message
        if not msg or not msg.document:
            return
        is_private = msg.chat.type == game.constants.ChatType.PRIVATE
        if not is_private:
            return
        doc = msg.document
        file_name = (doc.file_name or "").lower()
        if not file_name.endswith(".csv"):
            await self._tg.send_message(
                msg.chat.id,
                "⚠️ Поддерживаются только CSV-файлы. "
                "Отправьте файл с расширением .csv",
            )
            return
        user = msg.from_user
        telegram_id = user.id if user else 0
        chat_id = msg.chat.id
        try:
            await self._tg.send_message(chat_id, "⏳ Обработка CSV-файла...")
            file_path = await self._tg.get_file_path(doc.file_id)
            csv_content = await self._tg.download_file(file_path)
            service_responses = await self._content.handle_csv_upload(
                chat_id, telegram_id, csv_content
            )
            responses = bot.views.render_many(service_responses)
            await self._send_responses(responses)
        except Exception:
            logger.exception("CSV upload error")
            await self._tg.send_message(
                chat_id,
                "⚠️ Ошибка обработки файла. Проверьте формат CSV.",
            )

    async def _handle_message(self, update: clients.schemas.Update) -> None:
        msg = update.message
        if not msg or not msg.text:
            return

        chat_id = msg.chat.id
        text = msg.text.strip()
        user = msg.from_user
        telegram_id = user.id if user else 0
        username = user.first_name if user else "Неизвестный"
        is_private = msg.chat.type == game.constants.ChatType.PRIVATE

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
                bot_username=self._tg.bot_username,
            )
            if not responses:
                responses = self._chat_type_error(cmd, is_private, chat_id)
            results = await self._send_responses(responses)
            await self._capture_lobby_message_ids(responses, results)
            return

        if not is_private:
            responses = await self._gameplay.handle_possible_answer(
                chat_id, telegram_id, username, text
            )
            if responses:
                await self._send_responses(bot.views.render_many(responses))

    def _chat_type_error(
        self,
        cmd: str,
        is_private: bool,
        chat_id: int,
    ) -> list[game.schemas.GameResponse]:
        if not self._router.has_command(cmd, private=not is_private):
            return []
        if is_private:
            sr = game.schemas.ServiceResponse(
                chat_id=chat_id,
                view=game.constants.ViewName.GROUP_ONLY_COMMAND,
            )
        else:
            sr = game.schemas.ServiceResponse(
                chat_id=chat_id,
                view=game.constants.ViewName.PRIVATE_ONLY_COMMAND,
                payload={"bot_username": self._tg.bot_username},
            )
        return [bot.views.render(sr)]

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

        data = cb.data or ""
        chat_id = cb.message.chat.id if cb.message else 0
        message_id = cb.message.message_id if cb.message else 0
        telegram_id = cb.from_user.id
        username = cb.from_user.first_name
        if not chat_id:
            return

        responses = await self._router.dispatch_callback(
            data,
            chat_id=chat_id,
            telegram_id=telegram_id,
            username=username,
            bot_username=self._tg.bot_username,
            message_id=message_id,
        )

        alert_text: str | None = None
        chat_responses: list[game.schemas.GameResponse] = []
        for resp in responses:
            if resp.is_alert:
                if alert_text is None:
                    alert_text = resp.text
            else:
                chat_responses.append(resp)

        try:
            await self._tg.answer_callback(
                cb.id,
                text=alert_text,
                show_alert=alert_text is not None,
            )
        except (aiohttp.ClientError, OSError) as exc:
            logger.debug(
                "answerCallbackQuery failed (stale query), proceeding",
                exc_info=exc,
            )

        if chat_responses:
            results = await self._send_responses(chat_responses)
            await self._capture_lobby_message_ids(chat_responses, results)

    async def _handle_dialog_input(
        self,
        telegram_id: int,
        chat_id: int,
        text: str,
    ) -> list[game.schemas.GameResponse]:
        if text.startswith("/"):
            cmd = self._strip_mention(text.split(maxsplit=1)[0]).lower()
            if cmd in (
                f"/{game.constants.Command.CANCEL}",
                f"/{game.constants.Command.DONE}",
            ):
                self._dialog.clear(telegram_id)
                return bot.views.render_many(
                    [
                        game.schemas.ServiceResponse(
                            chat_id=chat_id,
                            view=game.constants.ViewName.DIALOG_CANCELLED,
                        )
                    ]
                )

        state = self._dialog.get(telegram_id)
        if not state:
            return []

        return await self._dispatch_dialog_step(
            state, telegram_id, chat_id, text
        )

    async def _dispatch_dialog_step(
        self,
        state: game.schemas.DialogState,
        telegram_id: int,
        chat_id: int,
        text: str,
    ) -> list[game.schemas.GameResponse]:
        step = state.step

        if step == game.constants.DialogStep.AWAIT_TOPIC_NAME:
            return await self._dialog_topic_name(telegram_id, chat_id, text)

        if step == game.constants.DialogStep.AWAIT_QUESTION_TEXT:
            state.question_text = text
            self._dialog.advance(
                telegram_id,
                game.constants.DialogStep.AWAIT_QUESTION_ANSWER,
            )
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id=chat_id,
                        view=game.constants.ViewName.DIALOG_PROMPT_ANSWER,
                    )
                ]
            )

        if step == game.constants.DialogStep.AWAIT_QUESTION_ANSWER:
            state.question_answer = text
            self._dialog.advance(
                telegram_id,
                game.constants.DialogStep.AWAIT_QUESTION_COST,
            )
            return bot.views.render_many(
                [
                    game.schemas.ServiceResponse(
                        chat_id=chat_id,
                        view=game.constants.ViewName.DIALOG_PROMPT_COST,
                    )
                ]
            )

        if step == game.constants.DialogStep.AWAIT_QUESTION_COST:
            return await self._dialog_question_cost(
                telegram_id, chat_id, text, state
            )

        self._dialog.clear(telegram_id)
        return []

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
                    text=(
                        "⚠️ Название темы не может быть пустым. "
                        "Попробуйте снова:"
                    ),
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
                    chat_id=chat_id,
                    text="⚠️ Нужно число. Попробуйте снова:",
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
    ) -> list[object]:
        tasks = []
        for resp in responses:
            if resp.edit_message_id:
                tasks.append(
                    self._tg.edit_message_text(
                        resp.chat_id,
                        resp.edit_message_id,
                        resp.text,
                        buttons=resp.keyboard,
                    )
                )
            elif resp.keyboard:
                tasks.append(
                    self._tg.send_keyboard(
                        resp.chat_id, resp.text, resp.keyboard
                    )
                )
            else:
                tasks.append(self._tg.send_message(resp.chat_id, resp.text))
        if not tasks:
            return []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                if isinstance(result, (aiohttp.ClientError, OSError)):
                    logger.warning(
                        "Network error sending to chat %d: %s",
                        responses[idx].chat_id,
                        result,
                    )
                else:
                    logger.error(
                        "Failed to send response to chat %d: %s",
                        responses[idx].chat_id,
                        result,
                        exc_info=result,
                    )
        return list(results)

    async def _capture_lobby_message_ids(
        self,
        responses: list[game.schemas.GameResponse],
        results: list[object],
    ) -> None:
        if not self._lobby:
            return
        for resp, result in zip(responses, results, strict=True):
            if (
                resp.lobby_game_id
                and isinstance(result, dict)
                and not resp.edit_message_id
            ):
                msg_id = result.get("message_id")
                if msg_id:
                    try:
                        await self._lobby.store_lobby_message_id(
                            resp.lobby_game_id, msg_id
                        )
                    except (sqlalchemy.exc.SQLAlchemyError, OSError) as exc:
                        logger.warning(
                            "Failed to store lobby message_id for game %s: %s",
                            resp.lobby_game_id,
                            exc,
                        )
