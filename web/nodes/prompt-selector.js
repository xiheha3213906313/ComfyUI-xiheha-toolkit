// XH_PromptSelector — scan source sidecars and pick a numbered positive/negative config.
import {
    SELECTOR_NODE,
    STACK_NODE,
    MODEL_SOURCE_NODE,
    PREVIEW_NODE,
    PREVIEW_INPUTS,
} from "../shared/constants.js";
import {
    createRoot,
    configureScrollableWidget,
    scrollWidgetOptions,
    hideWidget,
    widgetByName,
    widgetValue,
    markDirty,
    connectedNode,
    graphNodes,
    nodeTypeId,
    applyPortLabels,
    parseUiPayload,
} from "../shared/dom.js";
import { inspectSources } from "../shared/api.js";
import { collectSourceEntries } from "../shared/upstream.js";
import { rowToPreviewRow, previewHasAllInputsFrom } from "./prompt-preview.js";

export const NODE_ID = SELECTOR_NODE;

function sourceRowsFromInfos(infos, state) {
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

function selectorController(node) {
    if (node.__xhSelector) return node.__xhSelector;
    const root = createRoot("xh-selector");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    const domWidget = node.addDOMWidget("config_ui", "xh_config_ui", root, scrollWidgetOptions(node, 200));
    domWidget.element = root;
    configureScrollableWidget(node, root, scroll, { width: 400, height: 300 });
    hideWidget(widgetByName(node, "selection_state"));

    const controller = {
        node,
        root,
        scroll,
        infos: [],
        state: {},
        runtimeRows: null,
        refreshSequence: 0,
        error: null,
        readState() {
            try {
                const parsed = JSON.parse(String(widgetValue(node, "selection_state", "{}") || "{}"));
                this.state = {};
                if (parsed && typeof parsed === "object") {
                    for (const [name, value] of Object.entries(parsed)) {
                        this.state[name] = value == null || value === "" ? null : Number(value);
                    }
                }
            } catch {
                this.state = {};
            }
        },
        saveState() {
            const widget = widgetByName(node, "selection_state");
            if (widget) {
                const value = JSON.stringify(this.state);
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }
            markDirty(node);
        },
        getRows() {
            if (this.runtimeRows) return this.runtimeRows;
            return sourceRowsFromInfos(this.infos, this.state);
        },
        publish() {
            this.runtimeRows = sourceRowsFromInfos(this.infos, this.state);
            for (const target of graphNodes()) {
                if (nodeTypeId(target) !== PREVIEW_NODE) continue;
                const connected = PREVIEW_INPUTS.some((name) => connectedNode(target, name) === node);
                if (!connected) continue;
                if (previewHasAllInputsFrom(target, node)) target.__xhPreview?.setRows(this.getRows().map(rowToPreviewRow));
                else target.__xhPreview?.setRows([]);
            }
        },
        render() {
            scroll.textContent = "";
            if (this.error) {
                const error = document.createElement("div");
                error.className = "xh-error";
                error.textContent = this.error;
                scroll.appendChild(error);
                return;
            }
            if (!this.infos.length) {
                const empty = document.createElement("div");
                empty.className = "xh-muted";
                empty.textContent = "请连接来源获取节点";
                scroll.appendChild(empty);
                this.publish();
                return;
            }

            for (const info of this.infos) {
                const row = document.createElement("div");
                row.className = "xh-row";
                const title = document.createElement("span");
                title.className = "xh-model";
                title.textContent = info.display_name || info.source_name;
                row.appendChild(title);
                const buttons = document.createElement("div");
                buttons.className = "xh-buttons";
                const options = [{ label: "关闭", value: null }].concat(
                    (info.configs || []).map((config) => ({ label: `配置${config.index}`, value: Number(config.index) }))
                );
                for (const option of options) {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "xh-button" + (this.state[info.source_name] === option.value ? " selected" : "");
                    button.textContent = option.label;
                    button.onclick = () => {
                        this.state[info.source_name] = option.value;
                        this.runtimeRows = null;
                        this.saveState();
                        this.render();
                    };
                    buttons.appendChild(button);
                }
                if (!info.configs?.length) {
                    const noConfig = document.createElement("span");
                    noConfig.className = "xh-muted";
                    noConfig.textContent = "无配置";
                    buttons.appendChild(noConfig);
                }
                row.appendChild(buttons);
                scroll.appendChild(row);
            }
            this.publish();
        },
        async refreshFromSource() {
            const sequence = ++this.refreshSequence;
            const source = connectedNode(node, "source");
            if (!source || ![STACK_NODE, MODEL_SOURCE_NODE].includes(nodeTypeId(source))) {
                this.infos = [];
                this.error = null;
                this.runtimeRows = null;
                this.render();
                return;
            }
            const sources = collectSourceEntries(source);
            if (!sources.length) {
                this.infos = [];
                this.error = null;
                this.runtimeRows = null;
                this.render();
                return;
            }
            try {
                const infos = await inspectSources(sources);
                if (sequence !== this.refreshSequence) return;
                this.infos = infos;
                this.error = null;
                this.runtimeRows = null;
                for (const info of this.infos) {
                    const first = info.configs?.[0];
                    if (!(info.source_name in this.state)) this.state[info.source_name] = first ? Number(first.index) : null;
                    else if (this.state[info.source_name] != null && !info.configs?.some((config) => Number(config.index) === Number(this.state[info.source_name]))) {
                        this.state[info.source_name] = first ? Number(first.index) : null;
                    }
                }
                this.saveState();
                this.render();
            } catch (error) {
                if (sequence !== this.refreshSequence) return;
                this.error = error.message || String(error);
                this.render();
            }
        },
        setRowsFromExecution(rows) {
            this.runtimeRows = Array.isArray(rows) ? rows : [];
            for (const target of graphNodes()) {
                if (nodeTypeId(target) !== PREVIEW_NODE) continue;
                const connected = PREVIEW_INPUTS.some((name) => connectedNode(target, name) === node);
                if (!connected) continue;
                if (previewHasAllInputsFrom(target, node)) target.__xhPreview?.setRows(this.runtimeRows.map(rowToPreviewRow));
                else target.__xhPreview?.setRows([]);
            }
        },
    };
    controller.readState();
    node.__xhSelector = controller;
    controller.render();
    return controller;
}

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        selectorController(this);
        setTimeout(() => this.__xhSelector.refreshFromSource(), 0);
    };
    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        const rows = parseUiPayload(message, "xh_rows", null);
        if (rows && this.__xhSelector) this.__xhSelector.setRowsFromExecution(rows);
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhSelector?.refreshFromSource(), 0);
        return result;
    };
}
