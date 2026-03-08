from __future__ import annotations

import logging

import aiohttp

import clients.schemas

logger = logging.getLogger(__name__)

API_BASE = 'https://api.telegram.org/bot{token}/{method}'


class TgClient:
    def __init__(self, token: str):
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _url(self, method: str) -> str:
        return API_BASE.format(token=self._token, method=method)

    async def _request(self, method: str, **params) -> dict:
        url = self._url(method)
        async with self.session.get(url, params=params) as resp:
            data = await resp.json()
            if not data.get('ok'):
                logger.error('Telegram API error: %s', data)
                raise RuntimeError(
                    f'Telegram API error: {data.get("description")}',
                )
            return data['result']

    async def _post(
        self,
        method: str,
        payload: dict,
    ) -> dict:
        url = self._url(method)
        async with self.session.post(url, json=payload) as resp:
            data = await resp.json()
            if not data.get('ok'):
                logger.error('Telegram API error: %s', data)
                raise RuntimeError(
                    f'Telegram API error: {data.get("description")}',
                )
            return data['result']

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
    ) -> list[clients.schemas.Update]:
        params: dict = {'timeout': timeout}
        if offset is not None:
            params['offset'] = offset
        result = await self._request('getUpdates', **params)
        return [clients.schemas.Update.from_dict(u) for u in result]

    async def send_message(self, chat_id: int, text: str) -> dict:
        return await self._post('sendMessage', {
            'chat_id': chat_id,
            'text': text,
        })

    async def send_keyboard(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict]],
    ) -> dict:
        return await self._post('sendMessage', {
            'chat_id': chat_id,
            'text': text,
            'reply_markup': {
                'inline_keyboard': buttons,
            },
        })

    async def answer_callback(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> dict:
        payload: dict = {'callback_query_id': callback_query_id}
        if text is not None:
            payload['text'] = text
        return await self._post('answerCallbackQuery', payload)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
