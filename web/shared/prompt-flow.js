// Pure prompt row transforms plus graph-level prompt propagation.
import { PREVIEW_INPUTS } from "./constants.js";
import { connectedNode, graphNodes } from "./graph.js";

export function promptTokens(value) {
    return String(value ?? "")
        .split(/[,，]/)
        .map((item) => item.replace(/\s+/g, " ").trim())
        .filter(Boolean);
}

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

export function rowToPreviewRow(row) {
    const modelName = row.display_name || row.model_name || row.source_name || "";
    return {
        display_name: modelName,
        model_name: modelName,
        positive_tokens: row.positive_tokens || promptTokens(row.positive),
        negative_tokens: row.negative_tokens || promptTokens(row.negative),
        positive_enabled: Array.isArray(row.positive_enabled) ? row.positive_enabled : null,
        negative_enabled: Array.isArray(row.negative_enabled) ? row.negative_enabled : null,
    };
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
