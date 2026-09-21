// Workflow dirty-state notification isolated from ordinary DOM helpers.
import { app } from "../../../scripts/app.js";

export function markDirty(node, host = app) {
    if (!node) return;
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
    host.graph?.setDirtyCanvas?.(true, true);

    const capture = host.workflowManager?.activeWorkflow?.changeTracker?.captureCanvasState;
    if (typeof capture === "function") {
        try {
            capture.call(host.workflowManager.activeWorkflow.changeTracker);
            return;
        } catch {
            // Older/in-transition workflow managers can reject a capture;
            // use the graph API below as the compatibility fallback.
        }
    }
    host.graph?.change?.();
    host.graph?.afterChange?.();
}
