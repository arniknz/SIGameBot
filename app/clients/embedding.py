from __future__ import annotations

import logging

import httpx
import numpy

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300.0


class EmbeddingUnavailableError(Exception):
    pass


class EmbeddingClient:
    def __init__(
        self, base_url: str, timeout: float = _DEFAULT_TIMEOUT
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def encode(self, texts: list[str]) -> list[bytes]:
        if not texts:
            return []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.post(
                    f"{self._base_url}/encode",
                    json={"texts": texts},
                )
                r.raise_for_status()
                data = r.json()
        except httpx.ConnectError as e:
            raise EmbeddingUnavailableError(
                f"Embedding service unreachable at {self._base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise EmbeddingUnavailableError(
                f"Embedding service timeout at {self._base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise EmbeddingUnavailableError(
                f"Embedding service error {e.response.status_code}: {e}"
            ) from e
        vectors: list[list[float]] = data["vectors"]
        return [
            numpy.asarray(v, dtype=numpy.float32).tobytes() for v in vectors
        ]

    def check_health(self) -> None:
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{self._base_url}/health")
                r.raise_for_status()
        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as e:
            raise EmbeddingUnavailableError(
                f"Embedding service not reachable at {self._base_url}: {e}"
            ) from e


_backend: dict[str, EmbeddingClient] = {}


def set_embedding_backend(url: str) -> None:
    if not url:
        raise ValueError("EMBEDDING_SERVICE_URL must be set")
    _backend["instance"] = EmbeddingClient(url)


def get_embedding_backend() -> EmbeddingClient:
    instance = _backend.get("instance")
    if instance is None:
        raise RuntimeError(
            "Embedding backend not initialized;"
            " call set_embedding_backend at startup"
        )
    return instance
