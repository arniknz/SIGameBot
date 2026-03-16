from __future__ import annotations

import datetime
import logging
import random
import types

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.shop
import db.repositories.user
import game.constants
import game.models
import game.schemas
import game.shop_items
import sqlalchemy
import sqlalchemy.ext.asyncio

logger = logging.getLogger(__name__)


def _result(
    chat_id: int,
    view: game.constants.ViewName,
    *,
    edit_message_id: int | None = None,
    is_alert: bool = False,
    **payload: object,
) -> game.schemas.ServiceResponse:
    return game.schemas.ServiceResponse(
        chat_id=chat_id,
        view=view,
        payload=dict(payload),
        edit_message_id=edit_message_id,
        is_alert=is_alert,
    )


class ShopService:
    def __init__(
        self,
        session_factory: sqlalchemy.ext.asyncio.async_sessionmaker,
    ) -> None:
        self._session_factory = session_factory

    async def handle_shop_redirect(
        self,
        chat_id: int,
        bot_username: str,
    ) -> list[game.schemas.ServiceResponse]:
        return [
            _result(
                chat_id,
                game.constants.ViewName.SHOP_REDIRECT,
                bot_username=bot_username,
            )
        ]

    async def handle_shop_main(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_or_create(telegram_id, "")
            shop_repo = db.repositories.shop.ShopRepository(session)

            responses: list[game.schemas.ServiceResponse] = []
            daily = await self._try_claim_daily(user)
            if daily is not None:
                responses.append(daily)

            item_count = await shop_repo.count_unused_items(user.id)
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.SHOP_MAIN,
                    balance=user.balance,
                    item_count=item_count,
                )
            )
            return responses

    @staticmethod
    async def _try_claim_daily(
        user: game.models.UserModel,
    ) -> game.schemas.ServiceResponse | None:
        now = datetime.datetime.now(datetime.UTC)
        if user.last_daily_claim is not None:
            last = user.last_daily_claim
            if last.tzinfo is None:
                last = last.replace(tzinfo=datetime.UTC)
            if last.date() >= now.date():
                return None

        amount = game.constants.DAILY_REWARD_AMOUNT
        user.balance += amount
        user.last_daily_claim = now
        return _result(
            user.telegram_id,
            game.constants.ViewName.DAILY_REWARD_CLAIMED,
            amount=amount,
            new_balance=user.balance,
        )

    async def handle_shop_category(
        self,
        chat_id: int,
        telegram_id: int,
        category_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        try:
            category = game.constants.ShopCategory(category_str)
        except ValueError:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    is_alert=True,
                    text="⚠️ Неизвестная категория.",
                )
            ]

        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_or_create(telegram_id, "")

            items = game.shop_items.ITEMS_BY_CATEGORY.get(category, [])
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.SHOP_CATEGORY,
                    category=category,
                    items=items,
                    balance=user.balance,
                )
            ]

    async def handle_buy(
        self,
        chat_id: int,
        telegram_id: int,
        item_id_str: str,
    ) -> list[game.schemas.ServiceResponse]:
        try:
            item_id = int(item_id_str)
        except ValueError:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    is_alert=True,
                    text="⚠️ Неверный предмет.",
                )
            ]

        item_def = game.shop_items.ITEMS_BY_ID.get(item_id)
        if item_def is None:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    is_alert=True,
                    text="⚠️ Предмет не найден.",
                )
            ]

        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_or_create(telegram_id, "")
            shop_repo = db.repositories.shop.ShopRepository(session)

            if user.balance < item_def.price:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.SHOP_INSUFFICIENT,
                        balance=user.balance,
                        price=item_def.price,
                        item=item_def,
                    )
                ]

            inv = await shop_repo.purchase_item(
                user.id, item_def.id, item_def.price
            )
            if inv is None:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.SHOP_INSUFFICIENT,
                        balance=user.balance,
                        price=item_def.price,
                        item=item_def,
                    )
                ]

            logger.info(
                "User %s bought %s for %d (balance: %d)",
                telegram_id,
                item_def.name,
                item_def.price,
                user.balance,
            )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.SHOP_BUY_OK,
                    item=item_def,
                    new_balance=user.balance,
                )
            ]

    async def handle_balance(
        self,
        chat_id: int,
        telegram_id: int,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            user = await user_repo.get_or_create(telegram_id, "")
            shop_repo = db.repositories.shop.ShopRepository(session)

            responses: list[game.schemas.ServiceResponse] = []
            daily = await self._try_claim_daily(user)
            if daily is not None:
                responses.append(daily)

            item_count = await shop_repo.count_unused_items(user.id)
            responses.append(
                _result(
                    chat_id,
                    game.constants.ViewName.BALANCE_INFO,
                    balance=user.balance,
                    item_count=item_count,
                )
            )
            return responses

    async def handle_inventory_request(
        self,
        chat_id: int,
        telegram_id: int,
        username: str,
        *,
        message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            user_repo = db.repositories.user.UserRepository(session)
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )
            shop_repo = db.repositories.shop.ShopRepository(session)

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state(active_game.id)
            if (
                game_state is None
                or game_state.status != game.constants.GamePhase.WAITING_ANSWER
            ):
                return []

            participant = await participant_repo.get_by_telegram_id(
                active_game.id, telegram_id
            )
            if (
                participant is None
                or participant.id != game_state.buzzer_pressed_by
            ):
                return []

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return []

            inventory = await shop_repo.get_unused_inventory(user.id)
            if not inventory:
                return [
                    _result(
                        chat_id,
                        game.constants.ViewName.INVENTORY_EMPTY,
                        edit_message_id=message_id or None,
                    )
                ]

            item_counts: dict[int, int] = {}
            for inv in inventory:
                item_counts[inv.item_id] = item_counts.get(inv.item_id, 0) + 1

            items_display: list[dict] = []
            for item_id, count in sorted(item_counts.items()):
                item_def = game.shop_items.ITEMS_BY_ID.get(item_id)
                if item_def:
                    items_display.append(
                        {
                            "item_id": item_id,
                            "emoji": item_def.emoji,
                            "name": item_def.name,
                            "description": item_def.description,
                            "count": count,
                        }
                    )

            remaining_seconds = 0
            if game_state.timer_ends_at:
                now = datetime.datetime.now(datetime.UTC)
                remaining_seconds = max(
                    0,
                    int((game_state.timer_ends_at - now).total_seconds()),
                )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.INVENTORY_LIST,
                    edit_message_id=message_id or None,
                    items=items_display,
                    remaining_seconds=remaining_seconds,
                )
            ]

    async def handle_inventory_back(
        self,
        chat_id: int,
        telegram_id: int,
        *,
        message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        async with self._session_factory() as session, session.begin():
            game_repo = db.repositories.game.GameRepository(session)
            participant_repo = (
                db.repositories.participant.ParticipantRepository(session)
            )

            active_game = await game_repo.get_active_by_chat(chat_id)
            if (
                active_game is None
                or active_game.status != game.constants.GameStatus.ACTIVE
            ):
                return []

            game_state = await game_repo.get_state(active_game.id)
            if (
                game_state is None
                or game_state.status != game.constants.GamePhase.WAITING_ANSWER
            ):
                return []

            participant = await participant_repo.get_by_telegram_id(
                active_game.id, telegram_id
            )
            if (
                participant is None
                or participant.id != game_state.buzzer_pressed_by
            ):
                return []

            remaining_seconds = 0
            if game_state.timer_ends_at:
                now = datetime.datetime.now(datetime.UTC)
                remaining_seconds = max(
                    0,
                    int((game_state.timer_ends_at - now).total_seconds()),
                )

            return [
                _result(
                    chat_id,
                    game.constants.ViewName.ANSWER_PROMPT,
                    edit_message_id=message_id or None,
                    remaining_seconds=remaining_seconds,
                )
            ]

    async def handle_use_item(
        self,
        chat_id: int,
        telegram_id: int,
        item_id_str: str,
        *,
        message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        try:
            item_id = int(item_id_str)
        except ValueError:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    is_alert=True,
                    text="⚠️ Неверный предмет.",
                )
            ]
        item_def = game.shop_items.ITEMS_BY_ID.get(item_id)
        if item_def is None:
            return [
                _result(
                    chat_id,
                    game.constants.ViewName.PLAIN,
                    is_alert=True,
                    text="⚠️ Предмет не найден.",
                )
            ]
        async with self._session_factory() as session, session.begin():
            u = types.SimpleNamespace()
            u.session = session
            u.chat_id = chat_id
            u.telegram_id = telegram_id
            u.item_id = item_id
            u.message_id = message_id
            u.item_def = item_def
            u.user_repo = db.repositories.user.UserRepository(session)
            u.user = await u.user_repo.get_by_telegram_id(telegram_id)
            if u.user is None:
                return []
            u.shop_repo = db.repositories.shop.ShopRepository(session)
            u.inv_item = await u.shop_repo.get_unused_inventory_by_item(
                u.user.id, item_id
            )
            if u.inv_item is None:
                return [
                    _result(
                        u.chat_id,
                        game.constants.ViewName.PLAIN,
                        is_alert=True,
                        text="⚠️ У вас нет этого предмета.",
                    )
                ]
            u.game_data = await self._find_buzzer_game(u.session, u.telegram_id)
            if u.game_data is None:
                return [
                    _result(
                        u.chat_id,
                        game.constants.ViewName.PLAIN,
                        is_alert=True,
                        text="⚠️ Нет активной игры, где вы нажали звонок.",
                    )
                ]
            u.active_game, u.game_state, u.participant = u.game_data
            u.group_chat_id = u.active_game.chat_id
            await u.shop_repo.consume_item(u.inv_item, u.active_game.id)
            u.question_in_game_id = u.game_state.current_question_id
            await u.shop_repo.record_usage(
                game_id=u.active_game.id,
                participant_id=u.participant.id,
                item_id=u.item_id,
                inventory_id=u.inv_item.id,
                question_in_game_id=u.question_in_game_id,
            )
            u.remaining_seconds = 0
            if u.game_state.timer_ends_at:
                u.now = datetime.datetime.now(datetime.UTC)
                u.remaining_seconds = max(
                    0,
                    int((u.game_state.timer_ends_at - u.now).total_seconds()),
                )
            u.effect = game.constants.ItemEffect(u.item_def.effect)
            u.responses = await self._apply_immediate_effect(
                u.session,
                u.effect,
                u.item_def,
                u.active_game,
                u.game_state,
                u.participant,
                u.group_chat_id,
                u.telegram_id,
                u.remaining_seconds,
                message_id=u.message_id,
            )
            logger.info(
                "User %s used %s in game %s",
                u.telegram_id,
                u.item_def.name,
                u.active_game.id,
            )
            return u.responses

    async def _find_buzzer_game(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        telegram_id: int,
    ) -> (
        tuple[
            game.models.GameModel,
            game.models.GameStateModel,
            game.models.ParticipantModel,
        ]
        | None
    ):
        user_repo = db.repositories.user.UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            return None

        statement = (
            sqlalchemy.select(
                game.models.GameModel,
                game.models.GameStateModel,
                game.models.ParticipantModel,
            )
            .join(
                game.models.GameStateModel,
                game.models.GameStateModel.game_id == game.models.GameModel.id,
            )
            .join(
                game.models.ParticipantModel,
                sqlalchemy.and_(
                    game.models.ParticipantModel.game_id
                    == game.models.GameModel.id,
                    game.models.ParticipantModel.user_id == user.id,
                ),
            )
            .where(
                game.models.GameModel.status
                == game.constants.GameStatus.ACTIVE,
                game.models.GameStateModel.status
                == game.constants.GamePhase.WAITING_ANSWER,
                game.models.GameStateModel.buzzer_pressed_by
                == game.models.ParticipantModel.id,
            )
            .limit(1)
        )
        row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        return row[0], row[1], row[2]

    async def _apply_immediate_effect(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        effect: game.constants.ItemEffect,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        *,
        message_id: int = 0,
    ) -> list[game.schemas.ServiceResponse]:
        effect_text_ref: list[str] = [
            f"{item_def.emoji} {item_def.name} activated!"
        ]
        handlers = {
            game.constants.ItemEffect.EXTRA_TIME: self._ie_extra_time,
            game.constants.ItemEffect.REVEAL_HINT: self._ie_reveal_hint,
            game.constants.ItemEffect.REVEAL_ANSWER: self._ie_reveal_answer,
            game.constants.ItemEffect.BONUS_POINTS: self._ie_bonus_points,
            game.constants.ItemEffect.STEAL_POINTS: self._ie_steal_points,
            game.constants.ItemEffect.HIDE_SCORE: self._ie_hide_score,
            game.constants.ItemEffect.REPLACE_QUESTION: self._ie_replace,
            game.constants.ItemEffect.RESURRECT_QUESTION: self._ie_resurrect,
            game.constants.ItemEffect.OPEN_ANY: self._ie_open_any,
        }
        fn = handlers.get(effect)
        if fn is not None:
            out = await fn(
                session,
                item_def,
                active_game,
                game_state,
                participant,
                group_chat_id,
                telegram_id,
                remaining_seconds,
                message_id,
                effect_text_ref,
            )
            if out is not None:
                return out
        effect_text_ref[0] = (
            f"{item_def.emoji} {item_def.name} activated!\n"
            f"⏱ {remaining_seconds}s remaining"
            if effect not in handlers
            else effect_text_ref[0]
        )
        return self._ie_default(
            group_chat_id,
            item_def,
            remaining_seconds,
            message_id,
            effect_text_ref[0],
        )

    def _ie_default(
        self,
        group_chat_id: int,
        item_def: game.shop_items.ShopItemDef,
        remaining_seconds: int,
        message_id: int,
        effect_text: str,
    ) -> list[game.schemas.ServiceResponse]:
        edit_id = message_id or None
        return [
            _result(
                group_chat_id,
                game.constants.ViewName.ITEM_USED_GROUP,
                edit_message_id=edit_id,
                emoji=item_def.emoji,
                name=item_def.name,
                remaining_seconds=remaining_seconds,
                effect_text=effect_text,
            ),
        ]

    async def _ie_extra_time(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        if game_state.timer_ends_at:
            game_state.timer_ends_at += datetime.timedelta(
                seconds=game.shop_items.EXTRA_TIME_SECONDS,
            )
            remaining_seconds += game.shop_items.EXTRA_TIME_SECONDS
        effect_text_ref[0] = (
            f"{item_def.emoji} +{game.shop_items.EXTRA_TIME_SECONDS}s! "
            f"⏱ {remaining_seconds}s remaining"
        )
        return None

    async def _ie_reveal_hint(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        if not game_state.current_question_id:
            return None
        question_repo = db.repositories.question.QuestionRepository(session)
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if not detail:
            return None
        answer = detail[3]
        hint = answer[:3] + "..." if len(answer) > 3 else answer
        edit_id = message_id or None
        return [
            _result(
                group_chat_id,
                game.constants.ViewName.ITEM_USED_GROUP,
                edit_message_id=edit_id,
                emoji=item_def.emoji,
                name=item_def.name,
                remaining_seconds=remaining_seconds,
            ),
            _result(
                telegram_id,
                game.constants.ViewName.ITEM_USED,
                text=(
                    f"{item_def.emoji} Подсказка: «{hint}»\n"
                    f"⏱ Осталось {remaining_seconds} сек"
                ),
            ),
        ]

    async def _ie_reveal_answer(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        if not game_state.current_question_id:
            return None
        question_repo = db.repositories.question.QuestionRepository(session)
        detail = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if not detail:
            return None
        answer = detail[3]
        edit_id = message_id or None
        return [
            _result(
                group_chat_id,
                game.constants.ViewName.ITEM_USED_GROUP,
                edit_message_id=edit_id,
                emoji=item_def.emoji,
                name=item_def.name,
                remaining_seconds=remaining_seconds,
            ),
            _result(
                telegram_id,
                game.constants.ViewName.ITEM_USED,
                text=(
                    f"{item_def.emoji} Ответ: «{answer}»\n"
                    f"⏱ Осталось {remaining_seconds} сек"
                ),
            ),
        ]

    async def _ie_bonus_points(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        participant.score += game.shop_items.BONUS_START_POINTS
        effect_text_ref[0] = (
            f"{item_def.emoji} +{game.shop_items.BONUS_START_POINTS} очков!"
        )
        return None

    async def _ie_steal_points(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        participant_repo = db.repositories.participant.ParticipantRepository(
            session
        )
        players = await participant_repo.get_active_players(active_game.id)
        opponents = [p for p in players if p.id != participant.id]
        if opponents:
            victim = random.choice(opponents)
            victim.score -= game.shop_items.STEAL_AMOUNT
            participant.score += game.shop_items.STEAL_AMOUNT
            victim_user = await db.repositories.user.UserRepository(
                session
            ).get_by_id(victim.user_id)
            victim_name = victim_user.username if victim_user else "кого-то"
            effect_text_ref[0] = (
                f"{item_def.emoji} Украдено "
                f"{game.shop_items.STEAL_AMOUNT} очков у {victim_name}!"
            )
        return None

    async def _ie_hide_score(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        effect_text_ref[0] = f"{item_def.emoji} Ваш счёт теперь скрыт!"
        return None

    async def _ie_replace(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        if not game_state.current_question_id:
            return None
        question_repo = db.repositories.question.QuestionRepository(session)
        old_qig = await question_repo.get_question_in_game_detail(
            game_state.current_question_id,
        )
        if old_qig:
            old_qig[0].status = game.constants.QuestionInGameStatus.PENDING
            old_qig[0].asked_by = None
            old_qig[0].asked_at = None
        pending_board = await question_repo.get_pending_board(active_game.id)
        if not pending_board:
            return None
        new_qig_id = random.choice(pending_board)[0]
        new_detail = await question_repo.get_question_in_game_detail(new_qig_id)
        if not new_detail:
            return None
        new_qig = new_detail[0]
        new_qig.status = game.constants.QuestionInGameStatus.ASKED
        new_qig.asked_by = participant.id
        new_qig.asked_at = datetime.datetime.now(datetime.UTC)
        game_state.current_question_id = new_qig.id
        effect_text_ref[0] = (
            f"{item_def.emoji} Question replaced!\n"
            f"📢 {new_detail[1]}: {new_detail[2]}\n"
            f"💰 {new_detail[4]} pts"
        )
        return None

    async def _ie_resurrect(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        question_repo = db.repositories.question.QuestionRepository(session)
        answered = await question_repo.get_answered_in_game(active_game.id)
        if answered:
            revived = random.choice(answered)
            revived.status = game.constants.QuestionInGameStatus.PENDING
            revived.answered_by = None
            revived.answered_at = None
            effect_text_ref[0] = (
                f"{item_def.emoji} A question has been resurrected!"
            )
        return None

    async def _ie_open_any(
        self,
        session: sqlalchemy.ext.asyncio.AsyncSession,
        item_def: game.shop_items.ShopItemDef,
        active_game: game.models.GameModel,
        game_state: game.models.GameStateModel,
        participant: game.models.ParticipantModel,
        group_chat_id: int,
        telegram_id: int,
        remaining_seconds: int,
        message_id: int,
        effect_text_ref: list[str],
    ) -> list[game.schemas.ServiceResponse] | None:
        question_repo = db.repositories.question.QuestionRepository(session)
        pending_board = await question_repo.get_pending_board(active_game.id)
        if pending_board:
            new_qig_id = random.choice(pending_board)[0]
            new_detail = await question_repo.get_question_in_game_detail(
                new_qig_id
            )
            if new_detail:
                effect_text_ref[0] = (
                    f"{item_def.emoji} New question unlocked!\n"
                    f"📢 {new_detail[1]}: {new_detail[2]}\n"
                    f"💰 {new_detail[4]} pts"
                )
        return None
