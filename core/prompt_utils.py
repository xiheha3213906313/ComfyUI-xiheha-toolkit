"""Prompt cleanup and formatting functions shared by the nodes."""

from __future__ import annotations

import re
from collections.abc import Iterable


_PROMPT_SPLIT_RE = re.compile(r"[,，]")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_prompt_text(value: object) -> str:
    """Return a single-line prompt value without sidecar-only wrappers."""

    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        value = ", ".join(clean_prompt_text(item) for item in value if item is not None)

    text = str(value).replace("\ufeff", "").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text).strip()

    # Sidecar files sometimes quote a complete value. Do not remove
    # parentheses because they are meaningful in prompt syntax.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()

    if text.casefold() in {"none", "null"}:
        return ""
    return text


def join_prompt_values(values: Iterable[object]) -> str:
    """Join several config values while keeping the output usable as prompt text."""

    cleaned = [clean_prompt_text(value) for value in values]
    cleaned = [value for value in cleaned if value]
    return ", ".join(cleaned)


def split_prompt_tokens(text: object) -> list[str]:
    """Split a prompt on both ASCII and Chinese commas."""

    normalized = clean_prompt_text(text)
    if not normalized:
        return []
    return [token for token in (clean_prompt_text(x) for x in _PROMPT_SPLIT_RE.split(normalized)) if token]


def normalize_prompt_line(text: object) -> str:
    """Normalize one prompt line to comma-separated, single-line text."""

    return ", ".join(split_prompt_tokens(text))


def ensure_trailing_comma(text: object) -> str:
    """Normalize a prompt and append one ASCII comma when non-empty."""

    normalized = normalize_prompt_line(text)
    if not normalized:
        return ""
    return normalized if normalized.endswith(",") else normalized + ","


def split_prompt_lines(text: object) -> list[str]:
    """Split newline-delimited model prompt values, preserving empty lines."""

    if text is None:
        return []
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return value.split("\n")
