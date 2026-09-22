// XH_PromptConfigEditor node adapter. UI/state lives under features/prompt-config-editor.
import { CONFIG_EDITOR_NODE } from "../shared/constants.js";
import { afterNodeConfigure } from "../shared/lifecycle.js";
import { applyPortLabels } from "../shared/widgets.js";
import { createPromptConfigEditorController } from "../features/prompt-config-editor/controller.js";

export const NODE_ID = CONFIG_EDITOR_NODE;

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        createPromptConfigEditorController(this);
        setTimeout(() => this.__xhPromptConfigEditor?.refreshFromSource(), 0);
    };
    afterNodeConfigure(nodeType, function () {
        this.__xhPromptConfigEditor?.restoreFromWidgets?.();
    });
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhPromptConfigEditor?.refreshFromSource(), 0);
        return result;
    };
    const originalRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
        this.__xhPromptConfigEditor?.cleanup?.();
        return originalRemoved?.apply(this, arguments);
    };
}
