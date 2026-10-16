"""English-language detection, used for both input documents and generated summaries."""
from langdetect import DetectorFactory, LangDetectException, detect_langs

from .config import ENGLISH_MIN_PROBABILITY

DetectorFactory.seed = 0  # langdetect is non-deterministic without a fixed seed

_SAMPLE_CHARS = 20_000


def english_probability(text: str) -> float:
    try:
        candidates = detect_langs(text[:_SAMPLE_CHARS])
    except LangDetectException:
        return 0.0
    return next((c.prob for c in candidates if c.lang == "en"), 0.0)


def is_english(text: str, threshold: float = ENGLISH_MIN_PROBABILITY) -> bool:
    return english_probability(text) >= threshold
