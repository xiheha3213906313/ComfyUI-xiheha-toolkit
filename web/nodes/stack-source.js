// XH_StackSource — pass-through adapter for an external easy-use LORA_STACK.
import { STACK_NODE } from "../shared/constants.js";
import { applyPortLabels } from "../shared/widgets.js";
import { notifySelectorsForSourceChange } from "../shared/upstream.js";

export const NODE_ID = STACK_NODE;

const MIN_WIDTH = 150;

export function patch(nodeType) {
    const originalComputeSize = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function (out) {
        const originalTitle = this.title;
        this.title = "";
        let size;
        try {
            size = originalComputeSize ? originalComputeSize.apply(this, arguments) : (out || [0, 0]);
        } finally {
            this.title = originalTitle;
        }
        if (size) {
            size[0] = MIN_WIDTH;
            return size;
        }
        return [MIN_WIDTH, 60];
    };

    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        if (this.size) {
            this.size[0] = MIN_WIDTH;
        }
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
    };

    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
        const result = originalConfigure?.apply(this, arguments);
        if (this.size) {
            if (this.size[0] > MIN_WIDTH && this.size[0] <= 220) {
                this.size[0] = MIN_WIDTH;
            }
        }
        return result;
    };

    const originalResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
        if (size) {
            size[0] = Math.max(MIN_WIDTH, size[0]);
        }
        return originalResize?.apply(this, arguments);
    };

    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => notifySelectorsForSourceChange(this), 0);
        return result;
    };
}
