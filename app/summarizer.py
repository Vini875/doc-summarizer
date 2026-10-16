"""Abstractive + extractive summarization with Claude, followed by a quality review.

Pipeline for one document:
  1. Claude writes an abstractive summary and picks verbatim sentences for the extractive one.
  2. Code-level checks: extractive sentences must appear verbatim in the source, both
     summaries are capped at MAX_SUMMARY_WORDS, and both must be in English.
  3. Claude reviews the pair for relevance, correctness and completeness (1-5 each).
  4. If any check fails, the issues are fed back and the summary is regenerated
     (up to MAX_SUMMARY_ATTEMPTS). The best attempt is returned with its scores.
"""
import json
import re

import anthropic

from .config import (
    CLAUDE_EFFORT,
    CLAUDE_MODEL,
    MAX_SUMMARY_ATTEMPTS,
    MAX_SUMMARY_WORDS,
    QUALITY_PASS_SCORE,
)
from .language import is_english

# Server-side refusal fallback: if the model declines, the API reroutes within the same call.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client = anthropic.Anthropic(timeout=300.0)


class SummarizationError(RuntimeError):
    """Claude could not produce a usable summary."""


_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "abstractive_summary": {"type": "string"},
        "extractive_sentences": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["abstractive_summary", "extractive_sentences"],
    "additionalProperties": False,
}

_SCORES = {
    "type": "object",
    "properties": {
        "relevance": {"type": "integer"},
        "correctness": {"type": "integer"},
        "completeness": {"type": "integer"},
    },
    "required": ["relevance", "correctness", "completeness"],
    "additionalProperties": False,
}

_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "abstractive": _SCORES,
        "extractive": _SCORES,
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["abstractive", "extractive", "issues"],
    "additionalProperties": False,
}

_SUMMARY_INSTRUCTIONS = f"""Summarize the document above. Write everything in English.

Return two summaries:

1. abstractive_summary: a summary in your own words of at most {MAX_SUMMARY_WORDS} words.
   Cover the document's purpose, its main points, and any conclusions, findings,
   decisions or figures that matter. State only what the document supports; add no
   outside facts or opinions. Write in plain prose paragraphs.

2. extractive_sentences: the most important sentences from the document, copied
   exactly as they appear (same words, spelling and punctuation), listed in the order
   they occur in the document. Together they must total at most {MAX_SUMMARY_WORDS}
   words. Choose sentences that together cover the main points; avoid near-duplicates.
   Never paraphrase, merge, shorten or correct a sentence."""

_REVIEW_INSTRUCTIONS = f"""You are reviewing two summaries of the document above. Each was
limited to {MAX_SUMMARY_WORDS} words. The extractive summary consists of sentences copied from
the document; the abstractive summary is written in new words.

Score each summary from 1 (poor) to 5 (excellent) on:
- relevance: it focuses on what matters most in the document, with no filler or minor detail.
- correctness: every statement is supported by the document; nothing is invented or distorted.
- completeness: it covers the document's main points as fully as the word limit allows.

Then list concrete issues that would raise a low score (for example a missing key point or an
unsupported claim). Return an empty list if there are none.

<abstractive_summary>
{{abstractive}}
</abstractive_summary>

<extractive_summary>
{{extractive}}
</extractive_summary>"""


# ---------------------------------------------------------------------------
# Pure helpers (unit tested without calling the API)
# ---------------------------------------------------------------------------

def count_words(text: str) -> int:
    return len(text.split())


def _normalize(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def trim_to_word_limit(text: str, limit: int = MAX_SUMMARY_WORDS) -> str:
    """Cut text to at most `limit` words, ending on a sentence boundary where possible."""
    if count_words(text) <= limit:
        return text.strip()
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept, total = [], 0
    for sentence in sentences:
        words = count_words(sentence)
        if total + words > limit:
            break
        kept.append(sentence)
        total += words
    if kept:
        return " ".join(kept)
    return " ".join(text.split()[:limit])  # a single overlong sentence


def validate_extractive(sentences: list[str], source: str, limit: int = MAX_SUMMARY_WORDS) -> tuple[list[str], int]:
    """Keep only sentences found verbatim in the source, within the word limit.

    Returns (kept sentences, number rejected as not verbatim).
    """
    normalized_source = _normalize(source)
    kept, seen, rejected, total = [], set(), 0, 0
    for sentence in sentences:
        sentence = sentence.strip()
        key = _normalize(sentence)
        if not key or key in seen:
            continue
        if key not in normalized_source:
            rejected += 1
            continue
        words = count_words(sentence)
        if total + words > limit:
            break
        kept.append(sentence)
        seen.add(key)
        total += words
    return kept, rejected


# ---------------------------------------------------------------------------
# Claude calls
# ---------------------------------------------------------------------------

def _document_block(text: str) -> dict:
    # Same first block in both calls, so the review call reads the document from the prompt cache.
    return {
        "type": "text",
        "text": f"<document>\n{text}\n</document>",
        "cache_control": {"type": "ephemeral"},
    }


def _ask_claude(document_text: str, instructions: str, schema: dict) -> dict:
    try:
        response = _client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            betas=[_FALLBACK_BETA],
            fallbacks="default",
            output_config={
                "effort": CLAUDE_EFFORT,
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=[{
                "role": "user",
                "content": [_document_block(document_text), {"type": "text", "text": instructions}],
            }],
        )
    except anthropic.AuthenticationError as exc:
        raise SummarizationError("The Claude API key is missing or invalid. Check ANTHROPIC_API_KEY.") from exc
    except TypeError as exc:
        # The SDK raises TypeError before sending anything when no credentials are configured.
        if "authentication" not in str(exc):
            raise
        raise SummarizationError("The Claude API key is missing. Set ANTHROPIC_API_KEY in the .env file.") from exc
    except anthropic.RateLimitError as exc:
        raise SummarizationError("Claude is rate limiting requests. Please wait a minute and try again.") from exc
    except anthropic.BadRequestError as exc:
        raise SummarizationError(f"Claude rejected the request: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise SummarizationError(f"Claude API error ({exc.status_code}). Please try again later.") from exc
    except anthropic.APIConnectionError as exc:
        raise SummarizationError("Could not reach the Claude API. Check your network connection.") from exc

    if response.stop_reason == "refusal":
        raise SummarizationError("Claude declined to summarize this document.")
    if response.stop_reason == "max_tokens":
        raise SummarizationError("Claude's response was cut off before it finished. Please try again.")

    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SummarizationError("Claude returned a response that could not be parsed.") from exc


def _clamp_scores(scores: dict) -> dict:
    return {k: max(1, min(5, int(scores.get(k, 1)))) for k in ("relevance", "correctness", "completeness")}


def _summarize_once(document_text: str, feedback: list[str]) -> dict:
    instructions = _SUMMARY_INSTRUCTIONS
    if feedback:
        issues = "\n".join(f"- {issue}" for issue in feedback)
        instructions += f"\n\nA previous draft had these problems. Fix them in this version:\n{issues}"

    draft = _ask_claude(document_text, instructions, _SUMMARY_SCHEMA)

    issues: list[str] = []
    abstractive = draft["abstractive_summary"].strip()
    if count_words(abstractive) > MAX_SUMMARY_WORDS:
        issues.append(
            f"The abstractive summary was {count_words(abstractive)} words; "
            f"it must be at most {MAX_SUMMARY_WORDS}."
        )
        abstractive = trim_to_word_limit(abstractive)

    sentences, rejected = validate_extractive(draft["extractive_sentences"], document_text)
    if rejected:
        issues.append(
            f"{rejected} extractive sentence(s) were not copied exactly from the document and were removed."
        )
    if not sentences:
        issues.append("The extractive summary contained no sentences copied exactly from the document.")
    extractive = " ".join(sentences)

    if abstractive and not is_english(abstractive):
        issues.append("The abstractive summary must be written in English.")

    review = _ask_claude(
        document_text,
        _REVIEW_INSTRUCTIONS.format(abstractive=abstractive, extractive=extractive or "(empty)"),
        _REVIEW_SCHEMA,
    )
    scores = {
        "abstractive": _clamp_scores(review["abstractive"]),
        "extractive": _clamp_scores(review["extractive"]),
    }
    issues.extend(review["issues"])

    lowest = min(min(s.values()) for s in scores.values())
    passed = lowest >= QUALITY_PASS_SCORE and bool(extractive) and not rejected
    return {
        "abstractive": abstractive,
        "extractive": extractive,
        "scores": scores,
        "issues": issues,
        "passed": passed,
        "_rank": (passed, lowest, sum(sum(s.values()) for s in scores.values())),
    }


def summarize(document_text: str) -> dict:
    """Return the best summary found within MAX_SUMMARY_ATTEMPTS, with its quality report."""
    best, feedback = None, []
    for attempt in range(1, MAX_SUMMARY_ATTEMPTS + 1):
        result = _summarize_once(document_text, feedback)
        result["attempts"] = attempt
        if best is None or result["_rank"] > best["_rank"]:
            best = result
        if result["passed"]:
            break
        feedback = result["issues"]

    best.pop("_rank")
    best["model"] = CLAUDE_MODEL
    best["abstractive_words"] = count_words(best["abstractive"])
    best["extractive_words"] = count_words(best["extractive"])
    return best
