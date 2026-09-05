// Graph traversal, widget helpers, node sizing and style injection shared by every controller.
import { app } from "../../../scripts/app.js";
import { PORT_LABELS } from "./constants.js";
import { TOOLKIT_STYLES } from "./styles.js";

export const graphNodes = () => app.graph?._nodes || app.graph?.nodes || [];
export const nodeTypeId = (node) => node?.comfyClass || node?.type;

export function applyPortLabels(node) {
    const labels = PORT_LABELS[nodeTypeId(node)];
    if (!labels) return;
    for (const input of node.inputs || []) {
        const label = labels.inputs?.[input.name];
        if (label) input.label = label;
    }
    for (const [index, label] of (labels.outputs || []).entries()) {
        const output = node.outputs?.[index];
        if (output && label) output.label = label;
    }
}

export function enforceNodeMinimumSize(node, width, height) {
    if (!node?.setSize) return;
    node.__xhMinimumSize = { width, height };

    const clamp = (target) => {
        if (!target?.size || !target.setSize) return;
        const next = [
            Math.max(Number(target.size[0]) || 0, width),
            Math.max(Number(target.size[1]) || 0, height),
        ];
        if (next[0] !== target.size[0] || next[1] !== target.size[1]) target.setSize(next);
    };

    clamp(node);
    if (node.__xhSizeGuardInstalled) return;
    const originalResize = node.onResize;
    node.onResize = function (...args) {
        const result = originalResize?.apply(this, args);
        const minimum = this.__xhMinimumSize;
        if (minimum) clamp(this);
        return result;
    };
    node.__xhSizeGuardInstalled = true;
}

export function configureScrollableWidget(node, root, scroll, { width, height }) {
    root.style.width = "100%";
    root.style.maxWidth = "100%";
    root.style.height = "100%";
    root.style.maxHeight = "100%";
    root.style.minHeight = "0";
    root.style.display = "flex";
    root.style.flexDirection = "column";
    root.style.overflow = "hidden";
    scroll.style.width = "100%";
    scroll.style.maxWidth = "100%";
    scroll.style.height = "100%";
    scroll.style.maxHeight = "100%";
    scroll.style.minHeight = "0";
    scroll.style.flex = "1 1 auto";
    scroll.style.overflowY = "auto";
    scroll.style.overflowX = "hidden";
    enforceNodeMinimumSize(node, width, height);
    if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(() => enforceNodeMinimumSize(node, width, height));
    }
}

export function scrollWidgetOptions(node, minHeight = 180) {
    return {
        serialize: false,
        hideOnZoom: false,
        getMinHeight: () => minHeight,
        // ComfyUI recalculates this value while the node is resized. The
        // DOM root is height:100%, so the scroll view follows the node body.
        getMaxHeight: () => Math.max(minHeight, (Number(node.size?.[1]) || 300) - 75),
    };
}

export function widgetByName(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

export function widgetValue(node, name, fallback = "") {
    const widget = widgetByName(node, name);
    return widget ? widget.value : fallback;
}

export function markDirty(node) {
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    app.graph?.change?.();
}

export function connectedNode(node, inputName) {
    const input = node.inputs?.find((item) => item.name === inputName);
    if (!input || input.link == null) return null;
    const link = node.graph?.links?.[input.link] || app.graph?.links?.[input.link];
    if (!link) return null;
    return node.graph?.getNodeById?.(link.origin_id) || app.graph?.getNodeById?.(link.origin_id) || null;
}

export function isConnected(node, inputName) {
    return Boolean(node.inputs?.find((item) => item.name === inputName)?.link != null);
}

export function parseUiPayload(message, key, fallback) {
    const raw = message?.[key];
    if (!Array.isArray(raw) || raw.length === 0) return fallback;
    try {
        const value = typeof raw[0] === "string" ? JSON.parse(raw[0]) : raw[0];
        return value ?? fallback;
    } catch {
        return fallback;
    }
}

export function promptTokens(value) {
    return String(value ?? "")
        .split(/[,，]/)
        .map((item) => item.replace(/\s+/g, " ").trim())
        .filter(Boolean);
}

export function hideWidget(widget) {
    if (!widget || widget.__xhHidden) return;
    widget.__xhHidden = true;
    widget.hidden = true;
    const originalComputeSize = widget.computeSize;
    widget.computeSize = () => [0, 0];
    widget.__xhOriginalComputeSize = originalComputeSize;
}

export function installStyles() {
    if (document.getElementById("xh-styles")) return;
    const style = document.createElement("style");
    style.id = "xh-styles";
    style.textContent = TOOLKIT_STYLES;
    document.head.appendChild(style);
}

export function createRoot(className) {
    installStyles();
    const root = document.createElement("div");
    root.className = `xh-root ${className}`;
    return root;
}
