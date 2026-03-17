from __future__ import annotations

import game.models.base
import game.models.game
import game.models.question
import game.models.shop
import game.models.user

Base = game.models.base.Base
GameModel = game.models.game.GameModel
GameStateModel = game.models.game.GameStateModel
ParticipantModel = game.models.game.ParticipantModel
QuestionInGameModel = game.models.question.QuestionInGameModel
QuestionModel = game.models.question.QuestionModel
TopicModel = game.models.question.TopicModel
GameItemUsageModel = game.models.shop.GameItemUsageModel
ShopItemModel = game.models.shop.ShopItemModel
UserInventoryModel = game.models.shop.UserInventoryModel
UserModel = game.models.user.UserModel

__all__ = [
    "Base",
    "GameItemUsageModel",
    "GameModel",
    "GameStateModel",
    "ParticipantModel",
    "QuestionInGameModel",
    "QuestionModel",
    "ShopItemModel",
    "TopicModel",
    "UserInventoryModel",
    "UserModel",
]
