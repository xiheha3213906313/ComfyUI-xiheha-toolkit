"""Positive/negative prompt preview and final formatting node."""

from __future__ import annotations

import json
from typing import Any

try:
    from ..core.prompt_utils import ensure_trailing_comma, split_prompt_lines, split_prompt_tokens
except ImportError:  # Allows the test suite to import this module standalone.
    from core.prompt_utils import ensure_trailing_comma, split_prompt_lines, split_prompt_tokens


def build_preview_rows(
    model_names: object,
    positive_prompts: object,
    negative_prompts: object,
    token_state: object = "{}",
) -> list[dict[str, object]]:
    return _build_preview_rows(model_names, positive_prompts, negative_prompts, token_state)


def _read_token_state(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    return raw if isinstance(raw, dict) else {}


def preview_token_key(model_name: object, side: str, index: int) -> str:
    return f"{str(model_name or '').strip()}|{side}|{index}"


def _is_token_enabled(state: dict[str, Any], key: str) -> bool:
    value = state.get(key, True)
    return value not in (False, 0, "false", "False", "off", "关闭")


def _build_preview_rows(
    model_names: object,
    positive_prompts: object,
    negative_prompts: object,
    token_state: object,
) -> list[dict[str, object]]:
    names = split_prompt_lines(model_names)
    positives = split_prompt_lines(positive_prompts)
    negatives = split_prompt_lines(negative_prompts)
    state = _read_token_state(token_state)
    count = max(len(names), len(positives), len(negatives))
    rows: list[dict[str, object]] = []

    for index in range(count):
        model_name = names[index] if index < len(names) else f"模型{index + 1}"
        positive = positives[index] if index < len(positives) else ""
        negative = negatives[index] if index < len(negatives) else ""
        positive_tokens = split_prompt_tokens(positive)
        negative_tokens = split_prompt_tokens(negative)
        rows.append(
            {
                "model_name": model_name,
                "positive_tokens": positive_tokens,
                "negative_tokens": negative_tokens,
                "positive_enabled": [
                    _is_token_enabled(state, preview_token_key(model_name, "positive", token_index))
                    for token_index in range(len(positive_tokens))
                ],
                "negative_enabled": [
                    _is_token_enabled(state, preview_token_key(model_name, "negative", token_index))
                    for token_index in range(len(negative_tokens))
                ],
            }
        )
    return rows


class PromptPreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_names": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "模型名称"}),
                "positive_prompts": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "正向提示词"}),
                "negative_prompts": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "负向提示词"}),
                "token_state": ("STRING", {"default": "{}", "multiline": False, "hidden": True, "display_name": "提示词开关状态"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("正向提示词", "负向提示词")
    FUNCTION = "preview"
    CATEGORY = "xiheha-工具箱/提示词"

    def preview(self, model_names, positive_prompts, negative_prompts, token_state="{}"):  # noqa: ARG002
        rows = _build_preview_rows(model_names, positive_prompts, negative_prompts, token_state)
        positive = ensure_trailing_comma(", ".join(
            token
            for row in rows
            for index, token in enumerate(row["positive_tokens"])
            if row["positive_enabled"][index]
        ))
        negative = ensure_trailing_comma(", ".join(
            token
            for row in rows
            for index, token in enumerate(row["negative_tokens"])
            if row["negative_enabled"][index]
        ))
        rows_json = json.dumps(rows, ensure_ascii=False)
        return {
            "ui": {"xh_rows": [rows_json]},
            "result": (positive, negative),
        }
