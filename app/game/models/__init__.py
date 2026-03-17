from __future__ import annotations

import game.models.base as _base
import game.models.game as _game
import game.models.question as _question
import game.models.shop as _shop
import game.models.user as _user

Base = _base.Base
GameModel = _game.GameModel
GameStateModel = _game.GameStateModel
ParticipantModel = _game.ParticipantModel
QuestionInGameModel = _question.QuestionInGameModel
QuestionModel = _question.QuestionModel
TopicModel = _question.TopicModel
GameItemUsageModel = _shop.GameItemUsageModel
ShopItemModel = _shop.ShopItemModel
UserInventoryModel = _shop.UserInventoryModel
UserModel = _user.UserModel

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
