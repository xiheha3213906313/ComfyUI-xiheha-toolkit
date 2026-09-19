"""Interactive editor for model and LoRA prompt sidecar configurations."""

from __future__ import annotations


class PromptConfigEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": ("XH_SOURCE", {"display_name": "模型列表"}),
                "editor_state": (
                    "STRING",
                    {"default": "{}", "multiline": False, "hidden": True, "display_name": "配置编辑暂存状态"},
                ),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "edit"
    CATEGORY = "xiheha-工具箱/提示词"
    OUTPUT_NODE = True

    def edit(self, source, editor_state="{}"):  # noqa: ARG002
        return ()
