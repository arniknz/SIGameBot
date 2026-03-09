from __future__ import annotations

import logging

import bot.dialog
import clients.schemas
import clients.tg
import game.logic
import game.schemas

logger = logging.getLogger(__name__)

DB_ERROR_MSG = "⚠️ Bot is temporarily unavailable. Please try again later."


class Handlers:
    def __init__(
        self,
        tg: clients.tg.TgClient,
        logic: game.logic.GameLogic,
        dialog: bot.dialog.DialogManager,
    ):
        self._tg = tg
        self._logic = logic
        self._dialog = dialog

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
                    await self._tg.send_message(chat_id, DB_ERROR_MSG)
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
            if is_private:
                responses = await self._route_private_command(
                    command,
                    args.strip(),
                    chat_id,
                    telegram_id,
                )
            else:
                responses = await self._route_group_command(
                    command,
                    chat_id,
                    telegram_id,
                    username,
                )
            await self._send_responses(responses)
            return

        if not is_private:
            responses = await self._logic.handle_possible_answer(
                chat_id,
                telegram_id,
                username,
                text,
            )
            if responses:
                await self._send_responses(responses)

    @staticmethod
    def _strip_mention(command: str) -> str:
        at_pos = command.find("@")
        if at_pos != -1:
            return command[:at_pos]
        return command

    async def _route_group_command(
        self,
        command: str,
        chat_id: int,
        telegram_id: int,
        username: str,
    ) -> list[game.schemas.GameResponse]:
        match command:
            case "/start":
                return await self._logic.handle_start(
                    chat_id, telegram_id, username
                )
            case "/start_game":
                return await self._logic.handle_start_game(chat_id, telegram_id)
            case "/score":
                return await self._logic.handle_score(chat_id)
            case _:
                return []

    async def _route_private_command(
        self,
        command: str,
        args: str,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.GameResponse]:
        simple = {
            "/start": lambda: self._logic.handle_help(chat_id),
            "/my_games": lambda: self._logic.handle_my_games(
                chat_id, telegram_id
            ),
            "/add_question": lambda: self._logic.topic_keyboard_for_add(
                chat_id
            ),
            "/delete_topic": lambda: self._logic.handle_delete_topic(
                chat_id, telegram_id
            ),
            "/delete_question": lambda: self._logic.handle_delete_question(
                chat_id, telegram_id
            ),
            "/help": lambda: self._logic.handle_help(chat_id),
            "/rules": lambda: self._logic.handle_rules(chat_id),
        }
        handler = simple.get(command)
        if handler:
            return await handler()
        if command == "/add_topic":
            self._dialog.start_add_topic(telegram_id, game_chat_id=0)
            return [
                game.schemas.GameResponse(
                    chat_id=chat_id,
                    text="Enter the topic name:",
                )
            ]
        if command in ("/done", "/cancel"):
            self._dialog.clear(telegram_id)
            return [
                game.schemas.GameResponse(chat_id=chat_id, text="OK, done.")
            ]
        return [
            game.schemas.GameResponse(
                chat_id=chat_id,
                text="Use /help to see available commands.",
            )
        ]

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

        responses = await self._route_callback(
            chat_id, telegram_id, username, data
        )
        await self._send_responses(responses)

    async def _route_callback(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        data: str,
    ) -> list[game.schemas.GameResponse]:
        simple = {
            "join": lambda: self._logic.handle_join(
                chat_id, telegram_id, username
            ),
            "spectate": lambda: self._logic.handle_spectate(
                chat_id, telegram_id, username
            ),
            "leave": lambda: self._logic.handle_leave(
                chat_id, telegram_id, username
            ),
            "stop": lambda: self._logic.handle_stop(chat_id, telegram_id),
            "buzzer": lambda: self._logic.handle_buzzer(
                chat_id, telegram_id, username
            ),
            "help": lambda: self._logic.handle_help(chat_id),
            "rules": lambda: self._logic.handle_rules(chat_id),
        }
        handler = simple.get(data)
        if handler:
            return await handler()
        return await self._route_callback_prefixed(chat_id, telegram_id, data)

    async def _route_callback_prefixed(
        self,
        chat_id: int,
        telegram_id: int,
        data: str,
    ) -> list[game.schemas.GameResponse]:
        if data.startswith("q:"):
            return await self._logic.handle_question_selected(
                chat_id, telegram_id, data[2:]
            )
        if data.startswith("del_topic:"):
            return await self._logic.confirm_delete_topic(
                chat_id, telegram_id, data[10:]
            )
        if data.startswith("delq_topic:"):
            return await self._logic.list_questions_for_delete(
                chat_id, data[11:]
            )
        if data.startswith("delq_confirm:"):
            return await self._logic.confirm_delete_question(
                chat_id, telegram_id, data[13:]
            )
        if data.startswith("addq_topic:"):
            return self._handle_addq_topic_cb(chat_id, telegram_id, data[11:])
        return []

    def _handle_addq_topic_cb(
        self,
        chat_id: int,
        telegram_id: int,
        value: str,
    ) -> list[game.schemas.GameResponse]:
        if value == "cancel":
            return [
                game.schemas.GameResponse(chat_id=chat_id, text="Cancelled.")
            ]
        self._dialog.start_add_question(
            telegram_id, game_chat_id=0, topic_id=value
        )
        return [
            game.schemas.GameResponse(
                chat_id=chat_id,
                text="Send the question text:",
            )
        ]

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
                return [
                    game.schemas.GameResponse(
                        chat_id=chat_id,
                        text="OK, cancelled.",
                    )
                ]

        state = self._dialog.get(telegram_id)
        if not state:
            return []

        prompt: str | None = None
        match state.step:
            case bot.dialog.STEP_AWAIT_TOPIC_NAME:
                return await self._dialog_topic_name(telegram_id, chat_id, text)
            case bot.dialog.STEP_AWAIT_QUESTION_TEXT:
                state.question_text = text
                self._dialog.advance(
                    telegram_id, bot.dialog.STEP_AWAIT_QUESTION_ANSWER
                )
                prompt = "Now send the correct answer:"
            case bot.dialog.STEP_AWAIT_QUESTION_ANSWER:
                state.question_answer = text
                self._dialog.advance(
                    telegram_id, bot.dialog.STEP_AWAIT_QUESTION_COST
                )
                prompt = "Enter the point cost (e.g. 100, 200, 500):"
            case bot.dialog.STEP_AWAIT_QUESTION_COST:
                return await self._dialog_question_cost(
                    telegram_id, chat_id, text, state
                )
            case _:
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
        responses = await self._logic.handle_add_topic(
            chat_id, telegram_id, topic_name
        )
        self._dialog.clear(telegram_id)
        return responses

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
                    text="Must be a number. Try again:",
                )
            ]
        responses = await self._logic.handle_add_question(
            chat_id,
            telegram_id,
            state.topic_id,
            state.question_text,
            state.question_answer,
            cost,
        )
        self._dialog.clear(telegram_id)
        return responses

    async def _send_responses(
        self, responses: list[game.schemas.GameResponse]
    ) -> None:
        for resp in responses:
            try:
                if resp.keyboard:
                    await self._tg.send_keyboard(
                        resp.chat_id, resp.text, resp.keyboard
                    )
                else:
                    await self._tg.send_message(resp.chat_id, resp.text)
            except Exception:
                logger.exception(
                    "Failed to send response to chat %d",
                    resp.chat_id,
                )
