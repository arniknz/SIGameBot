from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10


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
                async with session.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
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
                        "max_tokens": 12,
                        "temperature": 0.0,
                    },
                ) as response:
                    data = await response.json()

                    if response.status != 200:
                        err = data.get("error", {})
                        logger.error(
                            "OpenRouter HTTP %d (model=%s): %s",
                            response.status,
                            self.model,
                            err.get("message", data),
                        )
                        return False

                    choices = data.get("choices") or []
                    if not choices:
                        logger.error(
                            "OpenRouter response has no choices (model=%s): %s",
                            self.model,
                            data,
                        )
                        return False

                    content = choices[0].get("message", {}).get("content")
                    if not content:
                        logger.error(
                            "OpenRouter returned empty content (model=%s, finish_reason=%s): %s",
                            self.model,
                            choices[0].get("finish_reason"),
                            data,
                        )
                        return False

                    return content.strip().upper().startswith("YES")
        except Exception:
            logger.exception(
                "OpenRouter API call failed (model=%s)",
                self.model,
            )
            return False


_backend: OpenRouterClient | None = None


def set_openrouter_client(client: OpenRouterClient) -> None:
    global _backend
    _backend = client


def get_openrouter_client() -> OpenRouterClient:
    if _backend is None:
        raise RuntimeError(
            "OpenRouter client not initialized; "
            "call set_openrouter_client at startup"
        )
    return _backend
