// XH_SmartVideoSplitter node adapter. Feature logic lives under features/smart-video-splitter.
import { SMART_SPLITTER_NODE } from "../shared/constants.js";
import { applyPortLabels } from "../shared/widgets.js";
import {
    getWidgetAtPos,
    hideTooltip,
    showTooltip as showTooltipCard,
    updateTooltipMutualExclusion,
} from "../shared/tooltip.js";
import {
    createSmartVideoSplitterController,
    resizeNodeToFit,
} from "../features/smart-video-splitter/controller.js";
import { MIN_HEIGHT, MIN_WIDTH } from "./smart-video-splitter-size.js";
import { enforceNodeMinimumSize } from "../shared/layout.js";

export const NODE_ID = SMART_SPLITTER_NODE;
export { MIN_HEIGHT, MIN_WIDTH, getWidgetAtPos, hideTooltip };

// Custom cards remain available, but native ComfyUI tooltips are the default.
export const ENABLE_CUSTOM_TOOLTIP = false;

export function showTooltip(data, clientX, clientY) {
    if (data && typeof data === "object") showTooltipCard(data, clientX, clientY);
}

export function setupWidgetTooltips() {
    // Registration is instance-scoped in the controller so external nodes are untouched.
}

export function applyTooltipMutualExclusion(node) {
    updateTooltipMutualExclusion(node);
}

export const splitterController = createSmartVideoSplitterController;

export function patch(nodeType) {
    setupWidgetTooltips();
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        createSmartVideoSplitterController(this, { customTooltip: ENABLE_CUSTOM_TOOLTIP });
        enforceNodeMinimumSize(this, MIN_WIDTH, MIN_HEIGHT);
        resizeNodeToFit(this);
    };
    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
        const result = originalConfigure?.apply(this, arguments);
        enforceNodeMinimumSize(this, MIN_WIDTH, MIN_HEIGHT);
        resizeNodeToFit(this);
        this.__xhSplitter?.restoreFromWidgets?.();
        applyTooltipMutualExclusion(this);
        return result;
    };
    const originalRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
        hideTooltip();
        this.__xhSplitter?.dispose?.();
        return originalRemoved?.apply(this, arguments);
    };
}
