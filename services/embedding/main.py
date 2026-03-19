from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from contextlib import asynccontextmanager
from functools import lru_cache

import numpy
import sentence_transformers
import torch
import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_WHITESPACE_PATTERN = re.compile(r"\s+")
_MODEL_HOLDER: dict[str, sentence_transformers.SentenceTransformer] = {}
_MODEL_LOCK = threading.Lock()


def _normalize(text: str) -> str:
    stripped = text.strip().lower()
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def _text_for_model(normalized: str) -> str:
    return normalized if normalized else " "


def get_model() -> sentence_transformers.SentenceTransformer:
    cached = _MODEL_HOLDER.get("instance")
    if cached is not None:
        return cached
    with _MODEL_LOCK:
        cached = _MODEL_HOLDER.get("instance")
        if cached is not None:
            return cached
        name = os.getenv(
            "SENTENCE_TRANSFORMER_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        fp16 = os.getenv("USE_FP16", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            "Loading sentence-transformers model %s (device=%s, fp16=%s)",
            name,
            device,
            fp16,
        )
        model = sentence_transformers.SentenceTransformer(
            name,
            device=device,
        )
        if fp16 and torch.cuda.is_available():
            model = model.half()
        _MODEL_HOLDER["instance"] = model
    return _MODEL_HOLDER["instance"]


_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))


@lru_cache(maxsize=_CACHE_SIZE)
def _encode_single_cached(text: str) -> bytes:
    model = get_model()
    vec = model.encode(
        [text],
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=1,
    )
    return numpy.asarray(vec[0], dtype=numpy.float32).tobytes()


class EncodeRequest(BaseModel):
    texts: list[str]


class EncodeResponse(BaseModel):
    vectors: list[list[float]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(
        target=get_model,
        name="embedding-model-load",
        daemon=True,
    ).start()
    await asyncio.sleep(0)
    yield


app = FastAPI(
    title="SIGameBot Embedding Service",
    version="1.1.0",
    lifespan=lifespan,
)


@app.post("/encode", response_model=EncodeResponse)
def encode(req: EncodeRequest) -> EncodeResponse:
    if not req.texts:
        return EncodeResponse(vectors=[])
    normalized = [_text_for_model(_normalize(t)) for t in req.texts]
    if len(normalized) == 1:
        raw = _encode_single_cached(normalized[0])
        arr = numpy.frombuffer(raw, dtype=numpy.float32)
        return EncodeResponse(vectors=[arr.tolist()])
    model = get_model()
    vectors = model.encode(
        normalized,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    arr = numpy.asarray(vectors, dtype=numpy.float32)
    return EncodeResponse(vectors=arr.tolist())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if "instance" not in _MODEL_HOLDER:
        return PlainTextResponse("model loading", status_code=503)
    return {"status": "ok"}


@app.get("/cache_stats")
def cache_stats() -> dict[str, int | None]:
    info = _encode_single_cached.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("EMBEDDING_PORT", "8001")),
        log_level="info",
    )
