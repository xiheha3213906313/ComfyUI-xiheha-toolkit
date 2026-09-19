"""Display positive and negative prompt strings in a dedicated node UI."""

from __future__ import annotations

import json


class PromptDisplay:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive_prompts": (
                    "STRING",
                    {"default": "", "multiline": True, "forceInput": True, "display_name": "正向提示词"},
                ),
                "negative_prompts": (
                    "STRING",
                    {"default": "", "multiline": True, "forceInput": True, "display_name": "负向提示词"},
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("正向提示词", "负向提示词")
    FUNCTION = "display"
    CATEGORY = "xiheha-工具箱/提示词"

    def display(self, positive_prompts, negative_prompts):
        values = tuple("" if value is None else str(value) for value in (positive_prompts, negative_prompts))
        return {
            "ui": {"xh_ports": [json.dumps(values, ensure_ascii=False)]},
            "result": values,
        }
