// Prompt row transforms plus graph-level prompt propagation.
import { promptTokens, rowToPreviewRow } from "../features/prompt-preview/state.js";
import { PREVIEW_INPUTS } from "./constants.js";
import { connectedNode, graphNodes } from "./graph.js";

export { promptTokens, rowToPreviewRow } from "../features/prompt-preview/state.js";

export function selectorRowsFromInfos(infos, state) {
    return infos
        .map((info) => {
            const selected = state[info.source_name];
            if (selected == null) return null;
            const config = info.configs?.find((item) => Number(item.index) === Number(selected));
            if (!config) return null;
            return {
                source_name: info.source_name,
                display_name: info.display_name,
                config_index: Number(config.index),
                positive: String(config.positive || ""),
                negative: String(config.negative || ""),
            };
        })
        .filter(Boolean);
}

export function previewHasAllInputsFrom(node, source = null) {
    if (!PREVIEW_INPUTS.every((name) => node.inputs?.find((item) => item.name === name)?.link != null)) return false;
    if (source == null) return true;
    return PREVIEW_INPUTS.every((name) => connectedNode(node, name) === source);
}

export function notifyPromptDisplays(changedNode = null) {
    for (const display of graphNodes()) {
        const controller = display.__xhPromptDisplay;
        if (!controller) continue;
        if (changedNode && !["positive_prompts", "negative_prompts"].some((name) => connectedNode(display, name) === changedNode)) continue;
        controller.refreshFromInputs();
    }
}
