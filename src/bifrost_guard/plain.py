"""Plain words (Law Rule 19): a rough reading-level check.

Uses the Flesch-Kincaid grade formula with a simple syllable count. A grade of 7 or less is
about what a 12-year-old reads comfortably.
"""
from __future__ import annotations

import re

MAX_GRADE = 7.0
_WORD = re.compile(r"[A-Za-z]+(?:'[a-z]+)?")


def _syllables(word: str) -> int:
    w = word.lower()
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def grade(text: str) -> float:
    sentences = [s for s in re.split(r"[.!?]+(?:\s|$)", text) if _WORD.search(s)]
    words = _WORD.findall(text)
    if len(words) < 6 or not sentences:  # the formula is meaningless on a few words
        return 0.0
    syl = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syl / len(words)) - 15.59


def is_plain(text: str) -> bool:
    return grade(text) <= MAX_GRADE
