// Generic Custom Hover Tooltip Engine for xiheha-toolkit nodes.
// Provides standalone glassmorphism card tooltips with zero leakage to external nodes.

import { app } from "../../../scripts/app.js";

const DEFAULT_HOVER_DELAY = 1000;
const registeredNodes = new Map();

let tooltipEl = null;
let hoverTimer = null;
let activeTarget = null;
let listenersInstalled = false;
let stylesheetInstalled = false;

/**
 * Ensure the independent stylesheet web/tooltip.css is dynamically loaded.
 */
export function ensureTooltipStylesheet() {
    if (stylesheetInstalled || typeof document === "undefined") return;
    if (document.getElementById("xh-tooltip-stylesheet")) {
        stylesheetInstalled = true;
        return;
    }
    const link = document.createElement("link");
    link.id = "xh-tooltip-stylesheet";
    link.rel = "stylesheet";
    link.href = new URL("../tooltip.css", import.meta.url).href;
    document.head.appendChild(link);
    stylesheetInstalled = true;
}

/**
 * Ensure singleton tooltip container in document body.
 */
export function ensureTooltipElement() {
    if (tooltipEl || typeof document === "undefined") return tooltipEl;
    tooltipEl = document.getElementById("xh-custom-tooltip");
    if (!tooltipEl) {
        tooltipEl = document.createElement("div");
        tooltipEl.id = "xh-custom-tooltip";
        tooltipEl.className = "xh-tooltip";
        document.body.appendChild(tooltipEl);
    }
    return tooltipEl;
}

/**
 * Parses a Python INPUT_TYPES multi-line tooltip string into structured card data.
 * Supports:
 *   【Title】or [Title]
 *   • Bullet points with optional key: value highlighting
 *   Plain descriptions
 */
export function parseTooltipString(tooltipStr, fallbackTitle = "参数说明") {
    if (!tooltipStr || typeof tooltipStr !== "string") return null;

    let text = tooltipStr.trim();
    let title = fallbackTitle;
    let badge = "参数说明";

    // 提取 【标题】 或 [标题]
    const headerMatch = text.match(/^【(.*?)】/) || text.match(/^\[(.*?)\]/);
    if (headerMatch) {
        title = headerMatch[1].trim();
        text = text.slice(headerMatch[0].length).trim();
    }

    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
    const descLines = [];
    const details = [];

    for (const line of lines) {
        if (line.startsWith("•") || line.startsWith("-") || line.startsWith("*")) {
            const content = line.replace(/^[•\-\*]\s*/, "");
            // 如果含有 冒号，将冒号前的关键词加粗
            const colonIdx = content.indexOf("：") !== -1 ? content.indexOf("：") : content.indexOf(":");
            if (colonIdx > 0 && colonIdx < 30) {
                const prefix = content.slice(0, colonIdx);
                const suffix = content.slice(colonIdx);
                details.push(`<b>${prefix}</b>${suffix}`);
            } else {
                details.push(content);
            }
        } else {
            descLines.push(line);
        }
    }

    return {
        title,
        badge,
        desc: descLines.join("<br>") || "暂无说明",
        details,
    };
}

/**
 * Resolves structured tooltip data for a widget:
 * 1. Check custom explicit dictionary
 * 2. Auto-parse Python w.tooltip / w.__xhOrigTooltip
 */
export function resolveTooltipData(widget, customTooltips = null) {
    if (!widget) return null;

    // 1. 显式自定义字典优先
    if (customTooltips && customTooltips[widget.name]) {
        const custom = customTooltips[widget.name];
        return {
            title: custom.title || widget.label || widget.name,
            badge: custom.badge || "参数说明",
            desc: custom.desc || "",
            details: custom.details || custom.items || [],
        };
    }

    // 2. 自动读取并解析 Python 原生 tooltip
    const rawTooltip = widget.__xhOrigTooltip || widget.tooltip || widget.options?.tooltip;
    if (rawTooltip && typeof rawTooltip === "string") {
        return parseTooltipString(rawTooltip, widget.label || widget.name);
    }

    return null;
}

/**
 * Find widget under canvas graph coordinates (gx, gy) on a given node.
 */
export function getWidgetAtPos(node, gx, gy) {
    if (!node || !node.widgets) return null;
    if (typeof node.getWidgetOnPos === "function") {
        const w = node.getWidgetOnPos(gx, gy);
        if (w) return w;
    }
    if (!node.pos || !node.size) return null;
    const nx = node.pos[0];
    const ny = node.pos[1];
    const nw = node.size[0];
    const relX = gx - nx;
    const relY = gy - ny;

    for (const w of node.widgets) {
        if (!w || w.hidden || w.type === "hidden" || w.last_y == null) continue;
        const wy = w.last_y;
        const wh = (w.computeSize ? w.computeSize(nw)[1] : 24) || 24;
        const margin = w.margin ?? 6;
        if (relX >= margin && relX <= nw - margin && relY >= wy && relY <= wy + wh) {
            return w;
        }
    }
    return null;
}

/**
 * Render HTML content for the tooltip card.
 */
export function renderTooltipContent(data) {
    let html = `
        <div class="xh-tooltip-header">
            <span class="xh-tooltip-title">${data.title}</span>
            <span class="xh-tooltip-badge">${data.badge}</span>
        </div>
        <div class="xh-tooltip-desc">${data.desc}</div>
    `;
    if (data.details && data.details.length > 0) {
        html += `<div class="xh-tooltip-detail">`;
        for (const item of data.details) {
            html += `<div class="xh-tooltip-item">${item}</div>`;
        }
        html += `</div>`;
    }
    return html;
}

/**
 * Display the custom tooltip card at the given screen coordinates.
 */
export function showTooltip(data, clientX, clientY) {
    const el = ensureTooltipElement();
    if (!el || !data) return;

    el.innerHTML = renderTooltipContent(data);
    el.style.display = "block";
    el.style.left = "-9999px";
    el.style.top = "-9999px";
    el.classList.remove("visible");

    const rect = el.getBoundingClientRect();
    const winW = (typeof window !== "undefined" && window.innerWidth) || 1920;
    const winH = (typeof window !== "undefined" && window.innerHeight) || 1080;

    const PADDING = 14;
    const OFFSET_X = 16;
    const OFFSET_Y = 16;

    let left = clientX + OFFSET_X;
    let top = clientY + OFFSET_Y;

    // 视口边界碰撞与翻转检测
    if (left + rect.width > winW - PADDING) {
        left = clientX - rect.width - 12;
    }
    if (left < PADDING) left = PADDING;

    if (top + rect.height > winH - PADDING) {
        top = clientY - rect.height - 12;
    }
    if (top < PADDING) top = PADDING;

    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(top)}px`;
    el.classList.add("visible");
}

/**
 * Hide the custom tooltip card.
 */
export function hideTooltip() {
    if (hoverTimer) {
        clearTimeout(hoverTimer);
        hoverTimer = null;
    }
    activeTarget = null;
    if (tooltipEl) {
        tooltipEl.classList.remove("visible");
        tooltipEl.style.display = "none";
        tooltipEl.innerHTML = "";
    }
}

/**
 * Find registered & enabled widget under pointer event.
 * STRICT ISOLATION GUARANTEE:
 * Returns null immediately if the node under pointer is not registered or not enabled.
 */
export function findRegisteredWidgetUnderPointer(e) {
    if (registeredNodes.size === 0) return null;

    const canvas = app?.canvas;
    if (!canvas || !canvas.graph) return null;
    const canvasEl = canvas.canvas;
    if (!canvasEl) return null;

    let gx, gy;
    if (typeof canvas.convertEventToCanvasOffset === "function") {
        const offset = canvas.convertEventToCanvasOffset(e);
        gx = offset[0];
        gy = offset[1];
    } else {
        const rect = canvasEl.getBoundingClientRect();
        const scale = canvas.ds?.scale || 1;
        const offset = canvas.ds?.offset || [0, 0];
        gx = (e.clientX - rect.left) / scale - offset[0];
        gy = (e.clientY - rect.top) / scale - offset[1];
    }

    let node = null;
    if (typeof canvas.graph.getNodeOnPos === "function") {
        node = canvas.graph.getNodeOnPos(gx, gy);
    }
    if (!node) {
        const list = canvas.graph._nodes || canvas.graph.nodes || [];
        for (const n of list) {
            if (!n || !n.pos || !n.size) continue;
            if (gx >= n.pos[0] && gx <= n.pos[0] + n.size[0] && gy >= n.pos[1] && gy <= n.pos[1] + n.size[1]) {
                node = n;
                break;
            }
        }
    }
    if (!node) return null;

    // 核心隔离断言：检查是否在当前插件已注册的节点列表中
    const config = registeredNodes.get(node);
    if (!config || !config.enabled) {
        // 未注册或未启用定制卡片的节点直接退出，绝不干涉其官方原生 Tooltip
        return null;
    }
    if (node.flags?.collapsed) return null;

    const w = getWidgetAtPos(node, gx, gy);
    if (!w) return null;

    const data = resolveTooltipData(w, config.tooltips);
    if (!data) return null;

    return {
        node,
        widget: w,
        name: w.name,
        data,
        clientX: e.clientX,
        clientY: e.clientY,
        hoverDelay: config.hoverDelay || DEFAULT_HOVER_DELAY,
    };
}

/**
 * Install global pointer listeners once lazily.
 * Uses passive/capture listeners without interfering with event propagation.
 */
export function ensureGlobalListeners() {
    if (listenersInstalled || typeof window === "undefined") return;
    listenersInstalled = true;

    window.addEventListener("pointermove", (e) => {
        const target = findRegisteredWidgetUnderPointer(e);
        if (!target) {
            hideTooltip();
            return;
        }

        if (activeTarget && activeTarget.node === target.node && activeTarget.name === target.name) {
            activeTarget.clientX = e.clientX;
            activeTarget.clientY = e.clientY;
            return;
        }

        hideTooltip();
        activeTarget = target;

        hoverTimer = setTimeout(() => {
            if (activeTarget && activeTarget.node === target.node && activeTarget.name === target.name) {
                showTooltip(target.data, activeTarget.clientX, activeTarget.clientY);
            }
        }, target.hoverDelay);
    }, { passive: true, capture: true });

    window.addEventListener("pointerdown", hideTooltip, { passive: true, capture: true });
    window.addEventListener("wheel", hideTooltip, { passive: true, capture: true });
    window.addEventListener("keydown", hideTooltip, { passive: true });
    window.addEventListener("pointerleave", hideTooltip, { passive: true });
}

/**
 * Apply or revert mutual exclusion on a specific node instance.
 * STRICT ISOLATION: Only operates on the passed node's widgets!
 */
export function updateTooltipMutualExclusion(node) {
    if (!node || !node.widgets) return;
    const config = registeredNodes.get(node);
    const isCustomEnabled = !!config?.enabled;

    for (const w of node.widgets) {
        if (!w) continue;

        // 如果传了显式白名单字典，仅处理字典中涵盖的参数；否则处理含 tooltip 的参数
        if (config?.tooltips && !config.tooltips[w.name]) {
            continue;
        }

        if (isCustomEnabled) {
            // 开启定制卡片时：将原生 widget.tooltip 暂存并置空，屏蔽官方原生浮窗
            if (w.tooltip) {
                w.__xhOrigTooltip = w.tooltip;
                w.tooltip = null;
            }
        } else {
            // 关闭定制卡片时：恢复原生 widget.tooltip，由 ComfyUI 官方浮窗呈现
            if (w.__xhOrigTooltip) {
                w.tooltip = w.__xhOrigTooltip;
            }
        }
    }
}

/**
 * Register a node to enable custom hover tooltips.
 * 
 * Usage in any node:
 *   registerCustomTooltip(this, {
 *       enabled: false,           // Set true to activate custom card; false for native ComfyUI tooltip
 *       hoverDelay: 1000,         // Hover delay in ms (default 1000ms)
 *       tooltips: WIDGET_TOOLTIPS // Optional custom dictionary; if omitted, parses w.tooltip automatically
 *   });
 */
export function registerCustomTooltip(node, options = {}) {
    if (!node) return;

    const config = {
        enabled: !!options.enabled,
        hoverDelay: options.hoverDelay || DEFAULT_HOVER_DELAY,
        tooltips: options.tooltips || null,
    };

    registeredNodes.set(node, config);

    if (config.enabled) {
        ensureTooltipStylesheet();
        ensureTooltipElement();
        ensureGlobalListeners();
    }

    updateTooltipMutualExclusion(node);

    // 节点被移除时自动注销，杜绝内存泄漏
    if (!node.__xhTooltipUnregisterHooked) {
        node.__xhTooltipUnregisterHooked = true;
        const originalOnRemoved = node.onRemoved;
        node.onRemoved = function () {
            unregisterCustomTooltip(this);
            return originalOnRemoved?.apply(this, arguments);
        };
    }
}

/**
 * Unregister a node and restore its native tooltips.
 */
export function unregisterCustomTooltip(node) {
    if (!node) return;
    const config = registeredNodes.get(node);
    if (config) {
        config.enabled = false;
        updateTooltipMutualExclusion(node);
        registeredNodes.delete(node);
    }
    if (activeTarget && activeTarget.node === node) {
        hideTooltip();
    }
}
