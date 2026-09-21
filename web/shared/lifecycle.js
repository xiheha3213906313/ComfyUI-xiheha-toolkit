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
