// Walk the graph to collect source entries and notify selectors when an upstream source changes.
import {
    STACK_NODE,
    MODEL_SOURCE_NODE,
    EASY_USE_STACK_NODE,
    SELECTOR_NODE,
    MODEL_LOADER_SOURCES,
} from "./constants.js";
import {
    graphNodes,
    nodeTypeId,
    widgetByName,
    widgetValue,
    connectedNode,
} from "./dom.js";

function collectEasyUseLocalSources(node) {
    const toggle = widgetValue(node, "toggle", true);
    if (toggle === false || toggle === "False" || toggle === "false" || toggle === 0) return [];
    const count = Math.max(1, Math.min(10, Number(widgetValue(node, "num_loras", 1)) || 1));
    const names = [];
    for (let index = 1; index <= count; index += 1) {
        const name = widgetValue(node, `lora_${index}_name`, "None");
        if (name && name !== "None") names.push(String(name));
    }
    return names;
}

export function collectStackNames(node, seen = new Set()) {
    if (!node || seen.has(node)) return [];
    const nextSeen = new Set(seen);
    nextSeen.add(node);

    // The toolkit node is only an adapter. Walk through it to the actual
    // easy-use stack node connected to its single input.
    if (nodeTypeId(node) === STACK_NODE) {
        return collectStackNames(connectedNode(node, "stack"), nextSeen);
    }

    const hasEasyUseWidgets = nodeTypeId(node) === EASY_USE_STACK_NODE || widgetByName(node, "num_loras");
    if (!hasEasyUseWidgets) return [];

    // easy-use itself can append to an earlier stack. Its cascade input port is
    // owned by the external easy-use plugin, so the name stays optional_lora_stack.
    const upstream = connectedNode(node, "optional_lora_stack");
    return [
        ...(upstream ? collectStackNames(upstream, nextSeen) : []),
        ...collectEasyUseLocalSources(node),
    ];
}

export function collectModelSources(node, seen = new Set()) {
    if (!node || seen.has(node)) return [];
    const nextSeen = new Set(seen);
    nextSeen.add(node);

    const loader = MODEL_LOADER_SOURCES[nodeTypeId(node)];
    if (loader) {
        const name = widgetValue(node, loader.widget, "");
        return name ? [{ source_name: String(name), folder_name: loader.folder_name }] : [];
    }

    const upstream = connectedNode(node, "model");
    return upstream ? collectModelSources(upstream, nextSeen) : [];
}

export function collectSourceEntries(source) {
    if (nodeTypeId(source) === STACK_NODE) {
        return collectStackNames(source).map((name) => ({ source_name: name, folder_name: "loras" }));
    }
    if (nodeTypeId(source) === MODEL_SOURCE_NODE) {
        return collectModelSources(connectedNode(source, "model"));
    }
    return [];
}

export function sourceDependsOnNode(source, changedNode, seen = new Set()) {
    if (!source || seen.has(source)) return false;
    if (source === changedNode) return true;
    const nextSeen = new Set(seen);
    nextSeen.add(source);

    if (nodeTypeId(source) === STACK_NODE) {
        return sourceDependsOnNode(connectedNode(source, "stack"), changedNode, nextSeen);
    }
    if (nodeTypeId(source) === MODEL_SOURCE_NODE) {
        return sourceDependsOnNode(connectedNode(source, "model"), changedNode, nextSeen);
    }
    return sourceDependsOnNode(connectedNode(source, "model"), changedNode, nextSeen);
}

function selectorUsesChangedSource(selector, changedNode) {
    return sourceDependsOnNode(connectedNode(selector, "source"), changedNode);
}

export function notifySelectorsForSourceChange(changedNode) {
    for (const selector of graphNodes()) {
        if (nodeTypeId(selector) === SELECTOR_NODE && selectorUsesChangedSource(selector, changedNode)) {
            selector.__xhSelector?.refreshFromSource();
        }
    }
}

function isModelLoaderWidget(node, name) {
    const loader = MODEL_LOADER_SOURCES[nodeTypeId(node)];
    return Boolean(loader && loader.widget === name);
}

export function installModelLoaderObserver(node) {
    if (node.__xhModelLoaderObserverInstalled) return;
    node.__xhModelLoaderObserverInstalled = true;

    const originalWidgetChanged = node.onWidgetChanged;
    node.onWidgetChanged = function (...args) {
        const result = originalWidgetChanged?.apply(this, args);
        if (isModelLoaderWidget(this, args[0])) notifySelectorsForSourceChange(this);
        return result;
    };

    const originalConnections = node.onConnectionsChange;
    node.onConnectionsChange = function (...args) {
        const result = originalConnections?.apply(this, args);
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
        return result;
    };

    for (const widget of node.widgets || []) {
        if (!isModelLoaderWidget(node, widget.name) || widget.__xhModelLoaderCallbackPatched) continue;
        const callback = widget.callback;
        widget.callback = (...args) => {
            const result = callback?.apply(widget, args);
            notifySelectorsForSourceChange(node);
            return result;
        };
        widget.__xhModelLoaderCallbackPatched = true;
    }
    notifySelectorsForSourceChange(node);
}

function isEasyUseSourceWidget(name) {
    return name === "toggle"
        || name === "mode"
        || name === "num_loras"
        || /^lora_\d+_(name|strength|model_strength|clip_strength)$/.test(name || "");
}

export function installEasyUseStackObserver(node) {
    if (node.__xhEasyUseObserverInstalled) return;
    node.__xhEasyUseObserverInstalled = true;

    const originalWidgetChanged = node.onWidgetChanged;
    node.onWidgetChanged = function (...args) {
        const result = originalWidgetChanged?.apply(this, args);
        if (isEasyUseSourceWidget(args[0])) notifySelectorsForSourceChange(this);
        return result;
    };

    const originalConnections = node.onConnectionsChange;
    node.onConnectionsChange = function (...args) {
        const result = originalConnections?.apply(this, args);
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
        return result;
    };

    // Older LiteGraph builds notify through widget.callback instead of
    // node.onWidgetChanged, so cover that path as well.
    for (const widget of node.widgets || []) {
        if (!isEasyUseSourceWidget(widget.name) || widget.__xhEasyUseCallbackPatched) continue;
        const callback = widget.callback;
        widget.callback = (...args) => {
            const result = callback?.apply(widget, args);
            notifySelectorsForSourceChange(node);
            return result;
        };
        widget.__xhEasyUseCallbackPatched = true;
    }
    notifySelectorsForSourceChange(node);
}
