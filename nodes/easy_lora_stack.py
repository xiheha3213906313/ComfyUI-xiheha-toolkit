"""easy-use-compatible source stack adapter node."""

from __future__ import annotations

try:
    from ..core.source_utils import stack_to_source
except ImportError:  # Allows the test suite to import this module standalone.
    from core.source_utils import stack_to_source


class StackSource:
    """Pass through an upstream easy-use stack and expose source metadata."""

    min_width = 180
    min_height = 60

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "stack": ("LORA_STACK", {"display_name": "Lora堆"}),
            },
        }

    RETURN_TYPES = ("LORA_STACK", "XH_SOURCE")
    RETURN_NAMES = ("Lora堆", "模型列表")
    FUNCTION = "get_source"
    CATEGORY = "xiheha-工具箱/模型列表获取"

    def get_source(self, stack):
        """Forward the upstream stack unchanged and mirror it as source data."""
        return stack, stack_to_source(stack)
