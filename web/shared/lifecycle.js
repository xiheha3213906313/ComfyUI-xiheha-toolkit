// Small idempotent cleanup registry for controller-owned listeners and wrappers.
export function createCleanupBag() {
    const cleanups = new Set();
    return {
        add(cleanup) {
            if (typeof cleanup === "function") cleanups.add(cleanup);
            return cleanup;
        },
        run() {
            for (const cleanup of [...cleanups].reverse()) {
                cleanups.delete(cleanup);
                cleanup();
            }
        },
        get size() {
            return cleanups.size;
        },
    };
}

export function afterNodeConfigure(nodeType, restore) {
    const originalConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
        const result = originalConfigure?.apply(this, arguments);
        restore?.apply(this, arguments);
        return result;
    };
}
