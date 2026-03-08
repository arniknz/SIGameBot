from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class Chat:
    id: int
    type: str
    title: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Chat:
        return cls(
            id=data['id'],
            type=data['type'],
            title=data.get('title'),
        )


@dataclasses.dataclass
class User:
    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> User:
        return cls(
            id=data['id'],
            is_bot=data['is_bot'],
            first_name=data['first_name'],
            last_name=data.get('last_name'),
            username=data.get('username'),
        )


@dataclasses.dataclass
class Message:
    message_id: int
    chat: Chat
    date: int
    from_user: User | None = None
    text: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        from_user = None
        if 'from' in data:
            from_user = User.from_dict(data['from'])
        return cls(
            message_id=data['message_id'],
            chat=Chat.from_dict(data['chat']),
            date=data['date'],
            from_user=from_user,
            text=data.get('text'),
        )


@dataclasses.dataclass
class CallbackQuery:
    id: str
    from_user: User
    data: str | None = None
    message: Message | None = None

    @classmethod
    def from_dict(cls, data: dict) -> CallbackQuery:
        message = None
        if 'message' in data:
            message = Message.from_dict(data['message'])
        return cls(
            id=data['id'],
            from_user=User.from_dict(data['from']),
            data=data.get('data'),
            message=message,
        )


@dataclasses.dataclass
class Update:
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Update:
        message = None
        callback_query = None
        if 'message' in data:
            message = Message.from_dict(data['message'])
        if 'callback_query' in data:
            callback_query = CallbackQuery.from_dict(data['callback_query'])
        return cls(
            update_id=data['update_id'],
            message=message,
            callback_query=callback_query,
        )
