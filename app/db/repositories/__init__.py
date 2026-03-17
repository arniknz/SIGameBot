from __future__ import annotations

import db.repositories.game
import db.repositories.participant
import db.repositories.question
import db.repositories.user

GameRepository = db.repositories.game.GameRepository
ParticipantRepository = db.repositories.participant.ParticipantRepository
QuestionRepository = db.repositories.question.QuestionRepository
UserRepository = db.repositories.user.UserRepository

__all__ = [
    "GameRepository",
    "ParticipantRepository",
    "QuestionRepository",
    "UserRepository",
]
