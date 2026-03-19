from __future__ import annotations

import difflib
import logging
import re

import nlp.openrouter

logger = logging.getLogger(__name__)

_WHITESPACE_PATTERN = re.compile(r"\s+")
_DEFAULT_FUZZY_RATIO_MIN = 0.76
_MIN_KEYWORD_LEN = 2


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


async def validate_player_answer(
    player_answer_raw: str,
    question_text: str,
    correct_answer_raw: str,
    *,
    max_question_word_overlap: float = 0.4,
    fuzzy_ratio_min: float = _DEFAULT_FUZZY_RATIO_MIN,
) -> bool:
    player = normalize_answer_text(player_answer_raw)
    correct = normalize_answer_text(correct_answer_raw)
    if not player or not correct:
        return False

    if player == correct or _fuzzy_or_substring_match(
        player, correct, fuzzy_ratio_min
    ):
        return True

    if normalize_answer_text(question_text):
        overlap = _question_word_overlap_ratio(player_answer_raw, question_text)
        if overlap > max_question_word_overlap:
            return False

    client = nlp.openrouter.get_openrouter_client()
    return await client.check_answer(
        question_text, correct_answer_raw, player_answer_raw
    )
