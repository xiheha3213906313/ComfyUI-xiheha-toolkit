// DOM widget layout, sizing, and root creation.
import { ensureToolkitStylesheet } from "./stylesheets.js";

export function enforceNodeMinimumSize(node, width, height) {
    if (!node?.setSize) return;
    node.__xhMinimumSize = { width, height };
    const clamp = (target) => {
        if (!target?.size || !target.setSize) return;
        const next = [
            Math.max(Number(target.size[0]) || 0, width),
            Math.max(Number(target.size[1]) || 0, height),
        ];
        if (next[0] !== target.size[0] || next[1] !== target.size[1]) target.setSize(next);
    };
    clamp(node);
    if (node.__xhSizeGuardInstalled) return;
    const originalResize = node.onResize;
    node.onResize = function (...args) {
        const result = originalResize?.apply(this, args);
        const minimum = this.__xhMinimumSize;
        if (minimum) clamp(this);
        return result;
    };
    node.__xhSizeGuardInstalled = true;
}

export function configureScrollableWidget(node, root, scroll, { width, height }) {
    Object.assign(root.style, {
        width: "100%", maxWidth: "100%", height: "100%", maxHeight: "100%",
        minHeight: "0", display: "flex", flexDirection: "column", overflow: "hidden",
    });
    Object.assign(scroll.style, {
        width: "100%", maxWidth: "100%", height: "100%", maxHeight: "100%",
        minHeight: "0", flex: "1 1 auto", overflowY: "auto", overflowX: "hidden",
    });
    enforceNodeMinimumSize(node, width, height);
    if (typeof requestAnimationFrame === "function") {
        requestAnimationFrame(() => enforceNodeMinimumSize(node, width, height));
    }
}

export function scrollWidgetOptions(node, minHeight = 180, reservedHeight = 75) {
    const reserved = Math.max(0, Number(reservedHeight) || 0);
    return {
        serialize: false,
        hideOnZoom: false,
        getMinHeight: () => minHeight,
        getMaxHeight: () => Math.max(minHeight, (Number(node.size?.[1]) || 300) - reserved),
    };
}

export function createRoot(className) {
    ensureToolkitStylesheet();
    const root = document.createElement("div");
    root.className = `xh-root ${className}`;
    return root;
}
