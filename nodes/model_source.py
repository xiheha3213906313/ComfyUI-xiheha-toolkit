"""Base model source adapter for prompt sidecar configuration."""

from __future__ import annotations

try:
    from ..core.source_utils import model_to_source
except ImportError:  # Allows the test suite to import this module standalone.
    from core.source_utils import model_to_source


class ModelSource:
    """Pass through a MODEL and expose its loaded source file as prompt data."""

    min_width = 180
    min_height = 60

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"display_name": "模型"}),
            }
        }

    RETURN_TYPES = ("MODEL", "XH_SOURCE")
    RETURN_NAMES = ("模型", "模型列表")
    FUNCTION = "get_source"
    CATEGORY = "xiheha-工具箱/模型列表获取"

    def get_source(self, model):
        return model, model_to_source(model)
