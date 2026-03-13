from __future__ import annotations

import asyncio
import logging
import typing

import aiohttp
import clients.schemas

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"

STARTUP_RETRIES = 10
STARTUP_DELAY = 3

SEND_RETRIES = 3
SEND_RETRY_DELAYS = (1, 2, 4)


class TgClient:
    def __init__(self, token: str):
        self._token = token
        self._session: aiohttp.ClientSession | None = None
        self.bot_username: str = ""

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(connector=connector)

        for attempt in range(1, STARTUP_RETRIES + 1):
            try:
                url = self._url("getMe")
                async with self._session.get(url) as resp:
                    data = await resp.json()
                    bot_name = data.get("result", {}).get("username", "")
                    self.bot_username = bot_name
                    logger.info("Telegram API connected (bot: @%s)", bot_name)
                    return
            except (aiohttp.ClientError, OSError) as exc:
                logger.warning(
                    "Telegram API not reachable (attempt %d/%d): %s",
                    attempt,
                    STARTUP_RETRIES,
                    exc,
                )
                if attempt < STARTUP_RETRIES:
                    await asyncio.sleep(STARTUP_DELAY)

        raise RuntimeError(
            f"Could not reach Telegram API after {STARTUP_RETRIES} attempts"
        )

    def _url(self, method: str) -> str:
        return API_BASE.format(token=self._token, method=method)

    async def _request(
        self, method: str, **params: typing.Any
    ) -> dict[str, typing.Any]:
        url = self._url(method)
        last_exc: Exception = RuntimeError("All GET retries exhausted")
        for attempt in range(SEND_RETRIES):
            try:
                async with self.session.get(url, params=params) as resp:
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.error("Telegram API error: %s", data)
                        raise RuntimeError(
                            f"Telegram API error: {data.get('description')}",
                        )
                    return data["result"]
            except (aiohttp.ClientError, OSError) as exc:
                last_exc = exc
                if attempt < SEND_RETRIES - 1:
                    delay = SEND_RETRY_DELAYS[attempt]
                    logger.warning(
                        "Telegram GET %s failed "
                        "(attempt %d/%d): %s "
                        "— retrying in %ds",
                        method,
                        attempt + 1,
                        SEND_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
        raise last_exc

    async def _post(
        self,
        method: str,
        payload: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        url = self._url(method)
        last_exc: Exception = RuntimeError("All POST retries exhausted")
        for attempt in range(SEND_RETRIES):
            try:
                async with self.session.post(url, json=payload) as resp:
                    data = await resp.json()
                    if not data.get("ok"):
                        logger.error("Telegram API error: %s", data)
                        raise RuntimeError(
                            f"Telegram API error: {data.get('description')}",
                        )
                    return data["result"]
            except (aiohttp.ClientError, OSError) as exc:
                last_exc = exc
                if attempt < SEND_RETRIES - 1:
                    delay = SEND_RETRY_DELAYS[attempt]
                    logger.warning(
                        "Telegram POST %s failed "
                        "(attempt %d/%d): %s "
                        "— retrying in %ds",
                        method,
                        attempt + 1,
                        SEND_RETRIES,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
        raise last_exc

    async def get_updates(
        self,
        offset: int | None = None,
        poll_timeout: int = 30,
    ) -> list[clients.schemas.Update]:
        params: dict[str, int] = {"timeout": poll_timeout}
        if offset is not None:
            params["offset"] = offset
        result = await self._request("getUpdates", **params)
        return [clients.schemas.Update.model_validate(u) for u in result]

    async def send_message(
        self, chat_id: int, text: str
    ) -> dict[str, typing.Any]:
        return await self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
            },
        )

    async def send_keyboard(
        self,
        chat_id: int,
        text: str,
        buttons: list[list[dict[str, str]]],
    ) -> dict[str, typing.Any]:
        return await self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {
                    "inline_keyboard": buttons,
                },
            },
        )

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        buttons: list[list[dict[str, str]]] | None = None,
    ) -> dict[str, typing.Any]:
        payload: dict[str, typing.Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if buttons is not None:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        return await self._post("editMessageText", payload)

    async def answer_callback(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> dict[str, typing.Any]:
        payload: dict[str, str] = {
            "callback_query_id": callback_query_id,
        }
        if text is not None:
            payload["text"] = text
        return await self._post("answerCallbackQuery", payload)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
