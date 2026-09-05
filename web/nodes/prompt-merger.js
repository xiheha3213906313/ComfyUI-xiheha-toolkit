// XH_PromptMerger — merge up to four prompt inputs with editable fallback boxes.
import { MERGE_NODE } from "../shared/constants.js";
import {
    createRoot,
    configureScrollableWidget,
    scrollWidgetOptions,
    hideWidget,
    widgetByName,
    widgetValue,
    markDirty,
    isConnected,
    parseUiPayload,
    applyPortLabels,
} from "../shared/dom.js";

export const NODE_ID = MERGE_NODE;

function mergeController(node) {
    if (node.__xhMerge) return node.__xhMerge;
    const root = createRoot("xh-merge");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    node.addDOMWidget("merge_ui", "xh_merge_ui", root, scrollWidgetOptions(node, 200));
    configureScrollableWidget(node, root, scroll, { width: 400, height: 300 });

    const controller = {
        node,
        scroll,
        fields: [],
        render(values = null) {
            const current = values || [1, 2, 3, 4].map((index) => widgetValue(node, `prompt_${index}`, ""));
            scroll.textContent = "";
            this.fields = [];
            current.forEach((value, index) => {
                const wrapper = document.createElement("div");
                wrapper.className = "xh-merge-row";
                const label = document.createElement("span");
                label.className = "xh-merge-label";
                label.textContent = `输入${index + 1}`;
                const textarea = document.createElement("textarea");
                textarea.className = "xh-merge-text";
                textarea.value = value || "";
                textarea.readOnly = isConnected(node, `prompt_${index + 1}`);
                textarea.oninput = () => {
                    if (!isConnected(node, `prompt_${index + 1}`)) {
                        const widget = widgetByName(node, `prompt_${index + 1}`);
                        if (widget) widget.value = textarea.value;
                        markDirty(node);
                    }
                };
                wrapper.append(label, textarea);
                scroll.appendChild(wrapper);
                this.fields.push(textarea);
            });
        },
        setValues(values) {
            if (!Array.isArray(values)) {
                this.render(null);
                return;
            }
            const fixedValues = values.slice(0, 4);
            while (fixedValues.length < 4) fixedValues.push("");
            this.render(fixedValues);
        },
    };
    [1, 2, 3, 4].forEach((index) => hideWidget(widgetByName(node, `prompt_${index}`)));
    node.__xhMerge = controller;
    controller.render();
    return controller;
}

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        mergeController(this);
    };
    const originalExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
        originalExecuted?.apply(this, arguments);
        const values = parseUiPayload(message, "xh_ports", null);
        if (values && this.__xhMerge) this.__xhMerge.setValues(values);
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhMerge?.render(), 0);
        return result;
    };
}
