"""xiheha-toolkit ComfyUI utility nodes."""

from .nodes.easy_lora_stack import StackSource
from .nodes.model_source import ModelSource
from .nodes.prompt_selector import PromptConfigSelector
from .nodes.prompt_preview import PromptPreview
from .nodes.prompt_merge import PromptMerger
from .nodes.prompt_display import PromptDisplay
from .server import register_routes

__version__ = "0.5.1"

NODE_CLASS_MAPPINGS = {
    "XH_StackSource": StackSource,
    "XH_ModelSource": ModelSource,
    "XH_PromptSelector": PromptConfigSelector,
    "XH_PromptPreview": PromptPreview,
    "XH_PromptMerger": PromptMerger,
    "XH_PromptDisplay": PromptDisplay,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "XH_StackSource": "easy-use兼容_模型列表获取",
    "XH_ModelSource": "模型列表获取",
    "XH_PromptSelector": "选择提示词配置",
    "XH_PromptPreview": "模型提示词控制",
    "XH_PromptMerger": "提示词合并",
    "XH_PromptDisplay": "显示提示词",
}

WEB_DIRECTORY = "./web"

register_routes()

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]

print(f"[xiheha-toolkit] v{__version__} loaded")
