// XH_PromptPreview — token-level enable/disable preview and final prompt formatting.
import { PREVIEW_NODE, SELECTOR_NODE, PREVIEW_INPUTS } from "../shared/constants.js";
import {
    createRoot,
    configureScrollableWidget,
    scrollWidgetOptions,
    hideWidget,
    widgetByName,
    widgetValue,
    markDirty,
    connectedNode,
    isConnected,
    parseUiPayload,
    promptTokens,
    nodeTypeId,
    applyPortLabels,
} from "../shared/dom.js";

export const NODE_ID = PREVIEW_NODE;

// Convert a selector row (or an execution row) into the shape the preview renders.
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

function previewTokenKey(modelName, side, index) {
    return `${String(modelName || "").trim()}|${side}|${index}`;
}

export function previewHasAllInputsFrom(node, source = null) {
    if (!PREVIEW_INPUTS.every((name) => isConnected(node, name))) return false;
    if (source == null) return true;
    return PREVIEW_INPUTS.every((name) => connectedNode(node, name) === source);
}

function previewController(node) {
    if (node.__xhPreview) return node.__xhPreview;
    const root = createRoot("xh-preview");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    node.addDOMWidget("preview_ui", "xh_preview_ui", root, scrollWidgetOptions(node, 200));
    configureScrollableWidget(node, root, scroll, { width: 400, height: 300 });
    hideWidget(widgetByName(node, "token_state"));

    const controller = {
        node,
        scroll,
        rows: [],
        tokenState: {},
        readTokenState() {
            try {
                const parsed = JSON.parse(String(widgetValue(node, "token_state", "{}") || "{}"));
                this.tokenState = parsed && typeof parsed === "object" ? parsed : {};
            } catch {
                this.tokenState = {};
            }
        },
        saveTokenState() {
            const widget = widgetByName(node, "token_state");
            const value = JSON.stringify(this.tokenState);
            if (widget) {
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }
            markDirty(node);
        },
        isTokenEnabled(row, side, index) {
            const key = previewTokenKey(row.model_name, side, index);
            if (Object.prototype.hasOwnProperty.call(this.tokenState, key)) {
                return this.tokenState[key] !== false;
            }
            const enabled = row[`${side}_enabled`];
            return !Array.isArray(enabled) || enabled[index] !== false;
        },
        setTokenEnabled(row, side, index, enabled) {
            const key = previewTokenKey(row.model_name, side, index);
            if (enabled) delete this.tokenState[key];
            else this.tokenState[key] = false;
            this.saveTokenState();
        },
        setRows(rows) {
            this.rows = Array.isArray(rows) ? rows.map(rowToPreviewRow) : [];
            this.render();
        },
        render() {
            scroll.textContent = "";
            if (!this.rows.length) {
                const empty = document.createElement("div");
                empty.className = "xh-muted";
                empty.textContent = "请输入模型名称、正向提示词和负向提示词";
                scroll.appendChild(empty);
                return;
            }
            for (const row of this.rows) {
                const positiveTokens = row.positive_tokens || [];
                const negativeTokens = row.negative_tokens || [];
                if (!positiveTokens.length && !negativeTokens.length) continue;
                const wrapper = document.createElement("div");
                wrapper.className = "xh-preview-row";
                const title = document.createElement("span");
                title.className = "xh-model";
                title.textContent = row.model_name || "未命名模型";
                wrapper.appendChild(title);
                if (positiveTokens.length) this.renderPrompt(wrapper, row, "正向", "positive", positiveTokens);
                if (negativeTokens.length) this.renderPrompt(wrapper, row, "负向", "negative", negativeTokens);
                scroll.appendChild(wrapper);
            }
        },
        renderPrompt(wrapper, row, label, side, tokens) {
            const sectionLabel = document.createElement("div");
            sectionLabel.className = "xh-section-label";
            sectionLabel.textContent = label;
            wrapper.appendChild(sectionLabel);
            const strip = document.createElement("div");
            strip.className = "xh-chip-strip";
            for (const [index, token] of tokens.entries()) {
                const chip = document.createElement("span");
                const enabled = this.isTokenEnabled(row, side, index);
                chip.className = `xh-chip${enabled ? "" : " disabled"}`;
                chip.textContent = token;
                chip.title = enabled ? "点击关闭提示词" : "点击启用提示词";
                chip.onclick = () => {
                    // Update only this chip. Rebuilding the whole preview
                    // resets every horizontal scroll position and causes a
                    // visible flicker for long prompt rows.
                    const nextEnabled = chip.classList.contains("disabled");
                    this.setTokenEnabled(row, side, index, nextEnabled);
                    chip.classList.toggle("disabled", !nextEnabled);
                    chip.title = nextEnabled ? "点击关闭提示词" : "点击启用提示词";
                };
                strip.appendChild(chip);
            }
            wrapper.appendChild(strip);
        },
        refreshFromUpstream() {
            if (!previewHasAllInputsFrom(node)) {
                this.setRows([]);
                return;
            }
            const source = connectedNode(node, "model_names");
            if (nodeTypeId(source) === SELECTOR_NODE && previewHasAllInputsFrom(node, source) && source.__xhSelector) {
                this.setRows(source.__xhSelector.getRows());
            } else {
                this.setRows([]);
            }
        },
    };
    controller.readTokenState();
    node.__xhPreview = controller;
    controller.render();
    return controller;
}

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        previewController(this);
        setTimeout(() => this.__xhPreview.refreshFromUpstream(), 0);
    };
    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        const rows = parseUiPayload(message, "xh_rows", null);
        if (rows && this.__xhPreview) {
            this.__xhPreview.setRows(previewHasAllInputsFrom(this) ? rows : []);
        }
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhPreview?.refreshFromUpstream(), 0);
        return result;
    };
}
