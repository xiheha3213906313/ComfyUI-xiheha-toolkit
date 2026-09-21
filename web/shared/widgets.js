// Widget lookup, labels, and visibility helpers.
import { PORT_LABELS } from "./constants.js";
import { nodeTypeId } from "./graph.js";

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
    if (labels.widgets) {
        for (const widget of node.widgets || []) {
            const label = labels.widgets[widget.name];
            if (label) widget.label = label;
        }
    }
}

export function widgetByName(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

export function widgetValue(node, name, fallback = "") {
    const widget = widgetByName(node, name);
    return widget ? widget.value : fallback;
}

export function hideWidget(widget) {
    if (!widget || widget.__xhHidden) return;
    widget.__xhHidden = true;
    widget.hidden = true;
    if (widget.element) widget.element.hidden = true;
    if (widget.__xhOriginalType === undefined) widget.__xhOriginalType = widget.type;
    if (widget.__xhOriginalComputeSize === undefined) {
        widget.__xhOriginalComputeSize = widget.computeSize;
        widget.__xhHasComputeSize = Object.prototype.hasOwnProperty.call(widget, "computeSize");
    }
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
}

export function showWidget(widget) {
    if (!widget || !widget.__xhHidden) return;
    widget.__xhHidden = false;
    widget.hidden = false;
    if (widget.element) widget.element.hidden = false;
    if (widget.__xhOriginalType !== undefined) {
        widget.type = widget.__xhOriginalType;
        delete widget.__xhOriginalType;
    }
    if (widget.__xhHasComputeSize && widget.__xhOriginalComputeSize) {
        widget.computeSize = widget.__xhOriginalComputeSize;
    } else {
        delete widget.computeSize;
    }
    delete widget.__xhOriginalComputeSize;
    delete widget.__xhHasComputeSize;
}
