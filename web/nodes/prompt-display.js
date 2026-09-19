// XH_PromptDisplay — show positive and negative prompt outputs in separate boxes.
import { DISPLAY_NODE, SELECTOR_NODE, PREVIEW_NODE } from "../shared/constants.js";
import {
    createRoot,
    configureScrollableWidget,
    scrollWidgetOptions,
    hideWidget,
    widgetByName,
    connectedOutput,
    parseUiPayload,
    promptTokens,
    nodeTypeId,
    applyPortLabels,
} from "../shared/dom.js";

export const NODE_ID = DISPLAY_NODE;

const INPUTS = [
    { name: "positive_prompts", label: "正向提示词" },
    { name: "negative_prompts", label: "负向提示词" },
];

function ensureTrailingComma(value) {
    const normalized = promptTokens(value).join(", ");
    return normalized ? `${normalized},` : "";
}

function selectorValue(source, slot) {
    const side = slot === 1 ? "positive" : slot === 2 ? "negative" : null;
    if (!side || !source.__xhSelector?.getRows) return "";
    return source.__xhSelector.getRows()
        .map((row) => ensureTrailingComma(row?.[side]))
        .join("\n");
}

function previewValue(source, slot) {
    const values = source.__xhPreview?.getOutputValues?.();
    return values?.[slot] || "";
}

function sourceValue(source, slot) {
    if (nodeTypeId(source) === SELECTOR_NODE) return selectorValue(source, slot);
    if (nodeTypeId(source) === PREVIEW_NODE) return previewValue(source, slot);
    return "";
}

function displayController(node) {
    if (node.__xhPromptDisplay) return node.__xhPromptDisplay;
    const root = createRoot("xh-display");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    node.addDOMWidget("display_ui", "xh_display_ui", root, scrollWidgetOptions(node, 200));
    configureScrollableWidget(node, root, scroll, { width: 400, height: 300 });

    const controller = {
        node,
        scroll,
        values: ["", ""],
        render() {
            scroll.textContent = "";
            INPUTS.forEach(({ label }, index) => {
                const row = document.createElement("div");
                row.className = "xh-display-row";
                const title = document.createElement("div");
                title.className = "xh-display-label";
                title.textContent = label;
                const textarea = document.createElement("textarea");
                textarea.className = "xh-display-text";
                textarea.readOnly = true;
                textarea.value = this.values[index];
                textarea.setAttribute("aria-label", label);
                row.append(title, textarea);
                scroll.appendChild(row);
            });
        },
        setValues(values) {
            this.values = INPUTS.map((_, index) => String(values?.[index] ?? ""));
            this.render();
        },
        refreshFromInputs() {
            this.setValues(INPUTS.map(({ name }) => {
                const output = connectedOutput(node, name);
                return output ? sourceValue(output.node, output.slot) : "";
            }));
        },
    };
    hideWidget(widgetByName(node, "positive_prompts"));
    hideWidget(widgetByName(node, "negative_prompts"));
    node.__xhPromptDisplay = controller;
    controller.render();
    return controller;
}

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        displayController(this);
        setTimeout(() => this.__xhPromptDisplay.refreshFromInputs(), 0);
    };
    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        const values = parseUiPayload(message, "xh_ports", null);
        if (values && this.__xhPromptDisplay) this.__xhPromptDisplay.setValues(values);
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhPromptDisplay?.refreshFromInputs(), 0);
        return result;
    };
}
