from __future__ import annotations

import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30


class OpenRouterClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def check_answer(
        self,
        question: str,
        correct_answer: str,
        player_answer: str,
    ) -> bool:
        prompt = (
            f"Вопрос: {question}\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Ответ игрока: {player_answer}\n\n"
            "Правильный ли ответ игрока? Учитывай синонимы, опечатки и "
            "разные формулировки.\n"
            "ВАЖНО: Если игрок просто перефразировал вопрос или задал,\n"
            "учитывай сложные моменты с городами, странами, etc.\n"
            "Встречный вопрос — отвечай NO.\n"
            "Отвечай только YES или NO."
        )

        timeout = aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                provider = os.getenv("OPENROUTER_HTTP_PROVIDER", "").strip()
                attempts = [provider] if provider else []
                attempts.append("")

                logger.info("OpenRouter check start (model=%s)", self.model)
                for provider_attempt in attempts:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    if provider_attempt:
                        headers["HTTP-Provider"] = provider_attempt

                    try:
                        async with session.post(
                            self.base_url,
                            headers=headers,
                            json={
                                "model": self.model,
                                "messages": [
                                    {
                                        "role": "system",
                                        "content": (
                                            "You are a strict but fair answer "
                                            "checker for a quiz game. "
                                            "Reply only with YES or NO."
                                        ),
                                    },
                                    {"role": "user", "content": prompt},
                                ],
                                "temperature": 0.0,
                                "stream": False,
                            },
                        ) as response:
                            data = await response.json()
                    except TimeoutError:
                        logger.error(
                            "OpenRouter timeout (model=%s, provider=%s)",
                            self.model,
                            provider_attempt or "auto",
                        )
                        continue

                    if response.status != 200:
                        err = data.get("error", {})
                        logger.error(
                            "OpenRouter HTTP %d (model=%s, provider=%s): %s",
                            response.status,
                            self.model,
                            provider_attempt or "auto",
                            err.get("message", data),
                        )
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        logger.error(
                            (
                                "OpenRouter response has no choices "
                                "(model=%s, provider=%s): %s"
                            ),
                            self.model,
                            provider_attempt or "auto",
                            data,
                        )
                        continue

                    message = choices[0].get("message", {})
                    content = message.get("content") or ""
                    if not content and "reasoning" in message:
                        content = message.get("reasoning") or ""
                        logger.debug("Using reasoning field instead of content")
                    if not content:
                        logger.error(
                            (
                                "OpenRouter returned empty content "
                                "(model=%s, provider=%s, "
                                "finish_reason=%s): %s"
                            ),
                            self.model,
                            provider_attempt or "auto",
                            choices[0].get("finish_reason"),
                            data,
                        )
                        logger.debug("OpenRouter full response: %s", data)
                        continue

                    result = content.strip().upper()
                    logger.info(
                        (
                            "OpenRouter check done "
                            "(model=%s, provider=%s, result=%s)"
                        ),
                        self.model,
                        provider_attempt or "auto",
                        result,
                    )
                    return result.startswith("YES")
                return False
        except Exception:
            logger.exception(
                "OpenRouter API call failed (model=%s)",
                self.model,
            )
            return False


_state: dict[str, OpenRouterClient | None] = {"backend": None}


def set_openrouter_client(client: OpenRouterClient) -> None:
    _state["backend"] = client


def get_openrouter_client() -> OpenRouterClient:
    backend = _state["backend"]
    if backend is None:
        raise RuntimeError(
            "OpenRouter client not initialized; "
            "call set_openrouter_client at startup"
        )
    return backend
