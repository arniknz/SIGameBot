from __future__ import annotations

import datetime
import uuid

import game.constants
import game.models
import game.shop_items
import sqlalchemy
import sqlalchemy.ext.asyncio


class ShopRepository:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:
        self._session = session

    async def get_balance(self, user_id: int) -> int:
        statement = sqlalchemy.select(game.models.UserModel.balance).where(
            game.models.UserModel.id == user_id,
        )
        result = (await self._session.execute(statement)).scalar_one_or_none()
        return result if result is not None else 0

    async def get_unused_inventory(
        self,
        user_id: int,
    ) -> list[game.models.UserInventoryModel]:
        statement = (
            sqlalchemy.select(game.models.UserInventoryModel)
            .where(
                game.models.UserInventoryModel.user_id == user_id,
                game.models.UserInventoryModel.used_at.is_(None),
            )
            .order_by(game.models.UserInventoryModel.purchased_at)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def get_unused_inventory_by_item(
        self,
        user_id: int,
        item_id: int,
    ) -> game.models.UserInventoryModel | None:
        statement = (
            sqlalchemy.select(game.models.UserInventoryModel)
            .where(
                game.models.UserInventoryModel.user_id == user_id,
                game.models.UserInventoryModel.item_id == item_id,
                game.models.UserInventoryModel.used_at.is_(None),
            )
            .order_by(game.models.UserInventoryModel.purchased_at)
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def purchase_item(
        self,
        user_id: int,
        item_id: int,
        price: int,
    ) -> game.models.UserInventoryModel | None:
        user_stmt = (
            sqlalchemy.select(game.models.UserModel)
            .where(game.models.UserModel.id == user_id)
            .with_for_update()
        )
        user = (await self._session.execute(user_stmt)).scalar_one_or_none()
        if user is None or user.balance < price:
            return None

        user.balance -= price

        inv = game.models.UserInventoryModel(
            user_id=user_id,
            item_id=item_id,
        )
        self._session.add(inv)
        await self._session.flush()
        return inv

    async def consume_item(
        self,
        inventory_item: game.models.UserInventoryModel,
        game_id: uuid.UUID,
    ) -> None:
        inventory_item.used_in_game_id = game_id
        inventory_item.used_at = datetime.datetime.now(datetime.UTC)

    async def record_usage(
        self,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
        item_id: int,
        inventory_id: uuid.UUID,
        question_in_game_id: uuid.UUID | None,
        effect_data: dict | None = None,
    ) -> game.models.GameItemUsageModel:
        usage = game.models.GameItemUsageModel(
            game_id=game_id,
            participant_id=participant_id,
            item_id=item_id,
            inventory_id=inventory_id,
            question_in_game_id=question_in_game_id,
            effect_data=effect_data,
        )
        self._session.add(usage)
        await self._session.flush()
        return usage

    async def get_active_effects(
        self,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
        question_in_game_id: uuid.UUID,
    ) -> list[game.models.GameItemUsageModel]:
        statement = (
            sqlalchemy.select(game.models.GameItemUsageModel)
            .join(
                game.models.ShopItemModel,
                game.models.GameItemUsageModel.item_id
                == game.models.ShopItemModel.id,
            )
            .where(
                game.models.GameItemUsageModel.game_id == game_id,
                game.models.GameItemUsageModel.participant_id == participant_id,
                game.models.GameItemUsageModel.question_in_game_id
                == question_in_game_id,
            )
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def get_pending_auto_buzzer(
        self,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> game.models.GameItemUsageModel | None:
        auto_buzzer_id = None
        for item_def in game.shop_items.SHOP_ITEMS:
            if item_def.effect == game.constants.ItemEffect.AUTO_BUZZER:
                auto_buzzer_id = item_def.id
                break
        if auto_buzzer_id is None:
            return None

        statement = (
            sqlalchemy.select(game.models.GameItemUsageModel)
            .where(
                game.models.GameItemUsageModel.game_id == game_id,
                game.models.GameItemUsageModel.participant_id == participant_id,
                game.models.GameItemUsageModel.item_id == auto_buzzer_id,
                game.models.GameItemUsageModel.question_in_game_id.is_(None),
            )
            .limit(1)
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_all_pending_auto_buzzers(
        self,
        game_id: uuid.UUID,
    ) -> list[game.models.GameItemUsageModel]:
        auto_buzzer_id = None
        for item_def in game.shop_items.SHOP_ITEMS:
            if item_def.effect == game.constants.ItemEffect.AUTO_BUZZER:
                auto_buzzer_id = item_def.id
                break
        if auto_buzzer_id is None:
            return []

        statement = (
            sqlalchemy.select(game.models.GameItemUsageModel)
            .where(
                game.models.GameItemUsageModel.game_id == game_id,
                game.models.GameItemUsageModel.item_id == auto_buzzer_id,
                game.models.GameItemUsageModel.question_in_game_id.is_(None),
            )
            .order_by(game.models.GameItemUsageModel.used_at)
            .limit(1)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def apply_game_scores_to_balances(
        self,
        game_id: uuid.UUID,
    ) -> list[tuple[str, int]]:
        statement = sqlalchemy.select(
            game.models.ParticipantModel.user_id,
            game.models.ParticipantModel.score,
        ).where(
            game.models.ParticipantModel.game_id == game_id,
            game.models.ParticipantModel.role
            == game.constants.ParticipantRole.PLAYER,
        )
        rows = (await self._session.execute(statement)).all()
        results: list[tuple[str, int]] = []
        for user_id, score in rows:
            await self._session.execute(
                sqlalchemy.update(game.models.UserModel)
                .where(game.models.UserModel.id == user_id)
                .values(
                    balance=game.models.UserModel.balance + score,
                )
            )
            user = await self._session.execute(
                sqlalchemy.select(game.models.UserModel.username).where(
                    game.models.UserModel.id == user_id,
                )
            )
            username = user.scalar_one_or_none() or "Unknown"
            results.append((username, score))
        return results

    async def count_unused_items(self, user_id: int) -> int:
        statement = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.UserInventoryModel)
            .where(
                game.models.UserInventoryModel.user_id == user_id,
                game.models.UserInventoryModel.used_at.is_(None),
            )
        )
        return (await self._session.execute(statement)).scalar_one()

    async def has_hide_score_active(
        self,
        game_id: uuid.UUID,
        participant_id: uuid.UUID,
    ) -> bool:
        hide_id = None
        for item_def in game.shop_items.SHOP_ITEMS:
            if item_def.effect == game.constants.ItemEffect.HIDE_SCORE:
                hide_id = item_def.id
                break
        if hide_id is None:
            return False

        statement = (
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(game.models.GameItemUsageModel)
            .where(
                game.models.GameItemUsageModel.game_id == game_id,
                game.models.GameItemUsageModel.participant_id == participant_id,
                game.models.GameItemUsageModel.item_id == hide_id,
            )
        )
        return (await self._session.execute(statement)).scalar_one() > 0
