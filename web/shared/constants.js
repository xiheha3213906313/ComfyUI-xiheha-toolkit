// Node type IDs, external loader mappings and port labels shared across the toolkit.
// Keep every value aligned with the Python registration in __init__.py.

export const STACK_NODE = "XH_StackSource";
export const MODEL_SOURCE_NODE = "XH_ModelSource";
// This ID belongs to the external easy-use plugin and must never be renamed here.
export const EASY_USE_STACK_NODE = "easy loraStack";
export const SELECTOR_NODE = "XH_PromptSelector";
export const PREVIEW_NODE = "XH_PromptPreview";
export const MERGE_NODE = "XH_PromptMerger";

export const MODEL_LOADER_SOURCES = {
    CheckpointLoaderSimple: { widget: "ckpt_name", folder_name: "checkpoints" },
    CheckpointLoader: { widget: "ckpt_name", folder_name: "checkpoints" },
    unCLIPCheckpointLoader: { widget: "ckpt_name", folder_name: "checkpoints" },
    UNETLoader: { widget: "unet_name", folder_name: "diffusion_models" },
};

export const PORT_LABELS = {
    [STACK_NODE]: {
        inputs: { stack: "Lora堆" },
        outputs: ["Lora堆", "模型列表"],
    },
    [MODEL_SOURCE_NODE]: {
        inputs: { model: "模型" },
        outputs: ["模型", "模型列表"],
    },
    [SELECTOR_NODE]: {
        inputs: { source: "模型列表" },
        outputs: ["模型名称", "正向提示词", "负向提示词"],
    },
    [PREVIEW_NODE]: {
        inputs: { model_names: "模型名称", positive_prompts: "正向提示词", negative_prompts: "负向提示词" },
        outputs: ["正向提示词", "负向提示词"],
    },
    [MERGE_NODE]: {
        inputs: { prompt_1: "提示词1", prompt_2: "提示词2", prompt_3: "提示词3", prompt_4: "提示词4" },
        outputs: ["合并提示词"],
    },
};

// The three string inputs the preview node requires before it can render live.
export const PREVIEW_INPUTS = ["model_names", "positive_prompts", "negative_prompts"];
