import { app } from "../../../../scripts/app.js";
import { ensureTooltipStylesheet } from "../stylesheets.js";
import { renderTooltipContent, resolveTooltipData } from "./data.js";

const DEFAULT_HOVER_DELAY = 1000;
const registeredNodes = new Map();
let tooltipElement = null;
let hoverTimer = null;
let activeTarget = null;
let listenersInstalled = false;

export function ensureTooltipElement() {
    if (tooltipElement || typeof document === "undefined") return tooltipElement;
    tooltipElement = document.getElementById("xh-custom-tooltip");
    if (!tooltipElement) {
        tooltipElement = document.createElement("div");
        tooltipElement.id = "xh-custom-tooltip";
        tooltipElement.className = "xh-tooltip";
        document.body.appendChild(tooltipElement);
    }
    return tooltipElement;
}

export function getWidgetAtPos(node, gx, gy) {
    if (!node?.widgets) return null;
    const direct = node.getWidgetOnPos?.(gx, gy);
    if (direct) return direct;
    if (!node.pos || !node.size) return null;
    const relativeX = gx - node.pos[0];
    const relativeY = gy - node.pos[1];
    for (const widget of node.widgets) {
        if (!widget || widget.hidden || widget.type === "hidden" || widget.last_y == null) continue;
        const height = (widget.computeSize?.(node.size[0])?.[1] || 24);
        const margin = widget.margin ?? 6;
        if (relativeX >= margin && relativeX <= node.size[0] - margin
            && relativeY >= widget.last_y && relativeY <= widget.last_y + height) return widget;
    }
    return null;
}

export function showTooltip(data, clientX, clientY) {
    const element = ensureTooltipElement();
    if (!element || !data) return;
    element.innerHTML = renderTooltipContent(data);
    element.style.display = "block";
    element.style.left = "-9999px";
    element.style.top = "-9999px";
    element.classList.remove("visible");
    const rect = element.getBoundingClientRect();
    const width = globalThis.window?.innerWidth || 1920;
    const height = globalThis.window?.innerHeight || 1080;
    let left = clientX + 16;
    let top = clientY + 16;
    if (left + rect.width > width - 14) left = clientX - rect.width - 12;
    if (top + rect.height > height - 14) top = clientY - rect.height - 12;
    element.style.left = `${Math.round(Math.max(14, left))}px`;
    element.style.top = `${Math.round(Math.max(14, top))}px`;
    element.classList.add("visible");
}

export function hideTooltip() {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = null;
    activeTarget = null;
    if (!tooltipElement) return;
    tooltipElement.classList.remove("visible");
    tooltipElement.style.display = "none";
    tooltipElement.textContent = "";
}

export function findRegisteredWidgetUnderPointer(event) {
    if (!registeredNodes.size) return null;
    const canvas = app?.canvas;
    const canvasElement = canvas?.canvas;
    if (!canvas?.graph || !canvasElement) return null;
    let gx;
    let gy;
    if (typeof canvas.convertEventToCanvasOffset === "function") {
        [gx, gy] = canvas.convertEventToCanvasOffset(event);
    } else {
        const rect = canvasElement.getBoundingClientRect();
        const scale = canvas.ds?.scale || 1;
        const offset = canvas.ds?.offset || [0, 0];
        gx = (event.clientX - rect.left) / scale - offset[0];
        gy = (event.clientY - rect.top) / scale - offset[1];
    }
    let node = canvas.graph.getNodeOnPos?.(gx, gy);
    if (!node) {
        node = (canvas.graph._nodes || canvas.graph.nodes || []).find((candidate) => candidate?.pos && candidate?.size
            && gx >= candidate.pos[0] && gx <= candidate.pos[0] + candidate.size[0]
            && gy >= candidate.pos[1] && gy <= candidate.pos[1] + candidate.size[1]);
    }
    const config = registeredNodes.get(node);
    if (!config?.enabled || node?.flags?.collapsed) return null;
    const widget = getWidgetAtPos(node, gx, gy);
    const data = resolveTooltipData(widget, config.tooltips);
    if (!widget || !data) return null;
    return {
        node, widget, name: widget.name, data,
        clientX: event.clientX, clientY: event.clientY,
        hoverDelay: config.hoverDelay,
    };
}

export function ensureGlobalListeners() {
    if (listenersInstalled || typeof window === "undefined") return;
    listenersInstalled = true;
    window.addEventListener("pointermove", (event) => {
        const target = findRegisteredWidgetUnderPointer(event);
        if (!target) { hideTooltip(); return; }
        if (activeTarget?.node === target.node && activeTarget?.name === target.name) {
            activeTarget.clientX = event.clientX;
            activeTarget.clientY = event.clientY;
            return;
        }
        hideTooltip();
        activeTarget = target;
        hoverTimer = setTimeout(() => {
            if (activeTarget?.node === target.node && activeTarget?.name === target.name) {
                showTooltip(target.data, activeTarget.clientX, activeTarget.clientY);
            }
        }, target.hoverDelay);
    }, { passive: true, capture: true });
    for (const eventName of ["pointerdown", "wheel", "keydown", "pointerleave"]) {
        window.addEventListener(eventName, hideTooltip, { passive: true, capture: eventName !== "keydown" });
    }
}

export function updateTooltipMutualExclusion(node) {
    if (!node?.widgets) return;
    const config = registeredNodes.get(node);
    for (const widget of node.widgets) {
        if (!widget || (config?.tooltips && !config.tooltips[widget.name])) continue;
        if (config?.enabled) {
            if (widget.tooltip) {
                widget.__xhOrigTooltip = widget.tooltip;
                widget.tooltip = null;
            }
        } else if (widget.__xhOrigTooltip) {
            widget.tooltip = widget.__xhOrigTooltip;
            delete widget.__xhOrigTooltip;
        }
    }
}

export function registerCustomTooltip(node, options = {}) {
    if (!node) return;
    const config = {
        enabled: Boolean(options.enabled),
        hoverDelay: Number(options.hoverDelay) || DEFAULT_HOVER_DELAY,
        tooltips: options.tooltips || null,
    };
    registeredNodes.set(node, config);
    if (config.enabled) {
        ensureTooltipStylesheet();
        ensureTooltipElement();
        ensureGlobalListeners();
    }
    updateTooltipMutualExclusion(node);
    if (node.__xhTooltipUnregisterHooked) return;
    node.__xhTooltipUnregisterHooked = true;
    const originalRemoved = node.onRemoved;
    node.onRemoved = function () {
        unregisterCustomTooltip(this);
        return originalRemoved?.apply(this, arguments);
    };
}

export function unregisterCustomTooltip(node) {
    if (!node) return;
    const config = registeredNodes.get(node);
    if (config) {
        config.enabled = false;
        updateTooltipMutualExclusion(node);
        registeredNodes.delete(node);
    }
    if (activeTarget?.node === node) hideTooltip();
}
