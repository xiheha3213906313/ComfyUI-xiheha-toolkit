"""Four-input prompt merger."""

from __future__ import annotations

import json

try:
    from ..core.prompt_utils import ensure_trailing_comma
except ImportError:  # Allows the test suite to import this module standalone.
    from core.prompt_utils import ensure_trailing_comma


class PromptMerger:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_1": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "提示词1"}),
            },
            "optional": {
                "prompt_2": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "提示词2"}),
                "prompt_3": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "提示词3"}),
                "prompt_4": ("STRING", {"default": "", "multiline": True, "forceInput": True, "display_name": "提示词4"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("合并提示词",)
    FUNCTION = "merge"
    CATEGORY = "xiheha-工具箱/提示词"

    def merge(self, prompt_1, prompt_2=None, prompt_3=None, prompt_4=None):
        port_values = [ensure_trailing_comma(value) for value in (prompt_1, prompt_2, prompt_3, prompt_4)]
        merged = " ".join(part for part in port_values if part)
        return {
            # Keep four positions in the UI payload so an empty port does
            # not make its corresponding preview box disappear after run.
            "ui": {"xh_ports": [json.dumps(port_values, ensure_ascii=False)]},
            "result": (merged,),
        }
