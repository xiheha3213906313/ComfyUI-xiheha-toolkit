// XH_StackSource — pass-through adapter for an external easy-use LORA_STACK.
import { STACK_NODE } from "../shared/constants.js";
import { applyPortLabels } from "../shared/dom.js";
import { notifySelectorsForSourceChange } from "../shared/upstream.js";

export const NODE_ID = STACK_NODE;

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
        return result;
    };
}
