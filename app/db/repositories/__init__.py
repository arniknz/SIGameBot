from __future__ import annotations

import db.repositories.game as _game
import db.repositories.participant as _participant
import db.repositories.question as _question
import db.repositories.user as _user

GameRepository = _game.GameRepository
ParticipantRepository = _participant.ParticipantRepository
QuestionRepository = _question.QuestionRepository
UserRepository = _user.UserRepository

__all__ = [
    "GameRepository",
    "ParticipantRepository",
    "QuestionRepository",
    "UserRepository",
]
