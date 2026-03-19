from __future__ import annotations

import difflib
import logging
import re

import clients.embedding
import numpy

logger = logging.getLogger(__name__)

_WHITESPACE_PATTERN = re.compile(r"\s+")
_REPEATED_CHAR = re.compile(r"(.)\1{2,}")
_DEFAULT_FUZZY_RATIO_MIN = 0.76
_MIN_CHARS_SEMANTIC = 4
_MIN_KEYWORD_LEN = 2

_CYR_TO_PHONETIC: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "j",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sh",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _collapse_repeated(text: str) -> str:
    return _REPEATED_CHAR.sub(r"\1\1", text)


def _phonetic_key(text: str) -> str:
    normalized = normalize_answer_text(text)
    collapsed = _collapse_repeated(normalized)
    result: list[str] = []
    for ch in collapsed:
        mapped = _CYR_TO_PHONETIC.get(ch)
        if mapped is not None:
            result.append(mapped)
        elif ch.isascii() and ch.isalpha():
            result.append(ch)
    return "".join(result)


def phonetic_match(
    player_text: str,
    correct_text: str,
    threshold: float = 0.6,
) -> bool:
    p_key = _phonetic_key(player_text)
    c_key = _phonetic_key(correct_text)
    if not p_key or not c_key:
        return False
    if p_key == c_key:
        return True
    ratio = difflib.SequenceMatcher(None, p_key, c_key).ratio()
    return ratio >= threshold


def normalize_answer_text(raw: str) -> str:
    stripped = raw.strip().lower()
    return _WHITESPACE_PATTERN.sub(" ", stripped).strip()


def _key_words(text: str) -> set[str]:
    normalized = normalize_answer_text(text)
    if not normalized:
        return set()
    return {
        w
        for w in _WHITESPACE_PATTERN.split(normalized)
        if len(w) >= _MIN_KEYWORD_LEN
    }


def _question_word_overlap_ratio(player_text: str, question_text: str) -> float:
    q_words = _key_words(question_text)
    if not q_words:
        return 0.0
    p_words = _key_words(player_text)
    overlap = sum(1 for w in q_words if w in p_words)
    return overlap / len(q_words)


def _text_for_model(normalized: str) -> str:
    return normalized if normalized else " "


def _question_similarity(
    player_text: str,
    question_text: str,
) -> float:
    player_n = normalize_answer_text(player_text)
    question_n = normalize_answer_text(question_text)
    if not player_n or not question_n:
        return 0.0
    return _embedding_similarity(question_n, player_n)


def build_answer_storage_fields(
    answer: str,
    model_name: str,
) -> tuple[str, bytes]:
    normalized = normalize_answer_text(answer)
    backend = clients.embedding.get_embedding_backend()
    raw = backend.encode([_text_for_model(normalized)])
    return normalized, raw[0]


def build_many_answer_storage_fields(
    answers: list[str],
    model_name: str,
) -> list[tuple[str, bytes]]:
    if not answers:
        return []
    normalized_list = [normalize_answer_text(a) for a in answers]
    to_encode = [_text_for_model(n) for n in normalized_list]
    backend = clients.embedding.get_embedding_backend()
    vectors = backend.encode(to_encode)
    return list(zip(normalized_list, vectors, strict=True))


def normalized_answers_equal(player_raw: str, correct_raw: str) -> bool:
    return normalize_answer_text(player_raw) == normalize_answer_text(
        correct_raw
    )


def answer_matches_stored_embedding(
    stored_embedding: bytes,
    player_answer_raw: str,
    threshold: float,
    model_name: str,
) -> bool:
    normalized_player = normalize_answer_text(player_answer_raw)
    if not normalized_player:
        return False
    backend = clients.embedding.get_embedding_backend()
    raw = backend.encode([_text_for_model(normalized_player)])
    stored = numpy.frombuffer(stored_embedding, dtype=numpy.float32)
    player = numpy.frombuffer(raw[0], dtype=numpy.float32)
    similarity = float(numpy.dot(stored, player))
    return similarity >= threshold


def _embedding_similarity(text_a: str, text_b: str) -> float:
    backend = clients.embedding.get_embedding_backend()
    raw = backend.encode([_text_for_model(text_a), _text_for_model(text_b)])
    a = numpy.frombuffer(raw[0], dtype=numpy.float32)
    b = numpy.frombuffer(raw[1], dtype=numpy.float32)
    return float(numpy.dot(a, b))


def _fuzzy_or_substring_match(
    player: str,
    correct: str,
    fuzzy_ratio_min: float,
) -> bool:
    if (
        difflib.SequenceMatcher(None, player, correct).ratio()
        >= fuzzy_ratio_min
    ):
        return True
    if len(correct) >= 4 and correct in player:
        return True
    return len(player) >= 4 and player in correct


def smart_answer_matches(
    player_answer_raw: str,
    correct_answer_raw: str,
    *,
    model_name: str,
    semantic_threshold: float,
    fuzzy_ratio_min: float = _DEFAULT_FUZZY_RATIO_MIN,
    min_chars_semantic: int = _MIN_CHARS_SEMANTIC,
    enable_phonetic: bool = False,
    phonetic_threshold: float = 0.6,
    phonetic_sim_low: float = 0.4,
    phonetic_sim_high: float = 0.7,
) -> bool:
    player = normalize_answer_text(player_answer_raw)
    correct = normalize_answer_text(correct_answer_raw)
    if not player or not correct:
        return False
    if player == correct or _fuzzy_or_substring_match(
        player, correct, fuzzy_ratio_min
    ):
        return True
    if len(player) < min_chars_semantic and len(correct) < min_chars_semantic:
        return False
    sim = _embedding_similarity(player, correct)
    if sim >= semantic_threshold:
        return True
    if (
        enable_phonetic
        and phonetic_sim_low <= sim <= phonetic_sim_high
        and phonetic_match(
            player_answer_raw,
            correct_answer_raw,
            phonetic_threshold,
        )
    ):
        logger.debug(
            "Phonetic fallback accepted: '%s' ≈ '%s' (sim=%.3f)",
            player_answer_raw,
            correct_answer_raw,
            sim,
        )
        return True
    return False


def validate_player_answer(
    player_answer_raw: str,
    question_text: str,
    correct_answer_raw: str,
    *,
    model_name: str,
    max_question_word_overlap: float,
    max_question_similarity: float,
    min_answer_similarity: float,
    fuzzy_ratio_min: float = _DEFAULT_FUZZY_RATIO_MIN,
    min_chars_semantic: int = _MIN_CHARS_SEMANTIC,
    enable_phonetic: bool = False,
    phonetic_threshold: float = 0.6,
) -> bool:
    if normalize_answer_text(question_text):
        overlap = _question_word_overlap_ratio(player_answer_raw, question_text)
        if overlap > max_question_word_overlap:
            return False
        q_sim = _question_similarity(player_answer_raw, question_text)
        if q_sim > max_question_similarity:
            return False
    return smart_answer_matches(
        player_answer_raw,
        correct_answer_raw,
        model_name=model_name,
        semantic_threshold=min_answer_similarity,
        fuzzy_ratio_min=fuzzy_ratio_min,
        min_chars_semantic=min_chars_semantic,
        enable_phonetic=enable_phonetic,
        phonetic_threshold=phonetic_threshold,
    )


def cosine_similarity_numpy(
    a: numpy.ndarray,
    b: numpy.ndarray,
) -> float:
    return float(numpy.dot(a, b))
