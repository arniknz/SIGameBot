from __future__ import annotations

import pydantic


class Chat(pydantic.BaseModel):
    id: int
    type: str
    title: str | None = None


class User(pydantic.BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None


class Message(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(populate_by_name=True)

    message_id: int
    chat: Chat
    date: int
    from_user: User | None = pydantic.Field(None, alias="from")
    text: str | None = None


class CallbackQuery(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(populate_by_name=True)

    id: str
    from_user: User = pydantic.Field(alias="from")
    data: str | None = None
    message: Message | None = None


class Update(pydantic.BaseModel):
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None
