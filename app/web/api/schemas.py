from __future__ import annotations

import datetime
import uuid

import pydantic


class TopicOut(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str


class TopicWithCountOut(TopicOut):
    question_count: int


class TopicCreate(pydantic.BaseModel):
    title: str = pydantic.Field(min_length=1, max_length=500)


class TopicUpdate(pydantic.BaseModel):
    title: str = pydantic.Field(min_length=1, max_length=500)


class QuestionOut(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    text: str
    answer: str
    cost: int
    topic_title: str | None = None


class QuestionCreate(pydantic.BaseModel):
    topic_id: uuid.UUID
    text: str = pydantic.Field(min_length=1)
    answer: str = pydantic.Field(min_length=1)
    cost: int = pydantic.Field(gt=0)


class QuestionUpdate(pydantic.BaseModel):
    topic_id: uuid.UUID | None = None
    text: str | None = pydantic.Field(default=None, min_length=1)
    answer: str | None = pydantic.Field(default=None, min_length=1)
    cost: int | None = pydantic.Field(default=None, gt=0)


class BulkImportResult(pydantic.BaseModel):
    created: int
    errors: list[str]


class UserOut(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    balance: int
    created_at: datetime.datetime


class GameOut(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)

    id: uuid.UUID
    chat_id: int
    status: str
    host_id: int | None
    created_at: datetime.datetime
    finished_at: datetime.datetime | None


class ParticipantOut(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: int
    role: str
    score: int
    is_active: bool
    joined_at: datetime.datetime
    username: str | None = None


class GameDetailOut(GameOut):
    participants: list[ParticipantOut]
    questions_total: int
    questions_answered: int


class ConfigOut(pydantic.BaseModel):
    question_selection_timeout: int
    buzzer_timeout: int
    answer_timeout: int


class ConfigUpdate(pydantic.BaseModel):
    question_selection_timeout: int | None = pydantic.Field(default=None, gt=0)
    buzzer_timeout: int | None = pydantic.Field(default=None, gt=0)
    answer_timeout: int | None = pydantic.Field(default=None, gt=0)
