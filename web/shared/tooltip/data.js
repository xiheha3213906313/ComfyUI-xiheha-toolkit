function text(value) {
    return typeof value === "string" ? value : "";
}

export function parseTooltipString(value, fallbackTitle = "参数说明") {
    if (typeof value !== "string" || !value.trim()) return null;
    let source = value.trim();
    let title = fallbackTitle;
    const header = source.match(/^【(.*?)】/) || source.match(/^\[(.*?)\]/);
    if (header) {
        title = header[1].trim() || fallbackTitle;
        source = source.slice(header[0].length).trim();
    }
    const description = [];
    const details = [];
    for (const rawLine of source.split("\n")) {
        const line = rawLine.trim();
        if (!line) continue;
        if (/^[•*-]/.test(line)) details.push(line.replace(/^[•*-]\s*/, ""));
        else description.push(line);
    }
    return {
        title,
        badge: "参数说明",
        desc: description.join("\n") || "暂无说明",
        details,
    };
}

export function resolveTooltipData(widget, customTooltips = null) {
    if (!widget) return null;
    const custom = customTooltips?.[widget.name];
    if (custom) {
        return {
            title: text(custom.title) || widget.label || widget.name,
            badge: text(custom.badge) || "参数说明",
            desc: text(custom.desc),
            details: Array.isArray(custom.details || custom.items)
                ? [...(custom.details || custom.items)].map(String)
                : [],
        };
    }
    const raw = widget.__xhOrigTooltip || widget.tooltip || widget.options?.tooltip;
    return parseTooltipString(raw, widget.label || widget.name);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    })[character]);
}

export function renderTooltipContent(data) {
    const details = (data?.details || [])
        .map((item) => `<div class="xh-tooltip-item">${escapeHtml(item)}</div>`)
        .join("");
    return `<div class="xh-tooltip-header"><span class="xh-tooltip-title">${escapeHtml(data?.title || "")}</span>`
        + `<span class="xh-tooltip-badge">${escapeHtml(data?.badge || "")}</span></div>`
        + `<div class="xh-tooltip-desc">${escapeHtml(data?.desc || "").replace(/\n/g, "<br>")}</div>`
        + (details ? `<div class="xh-tooltip-detail">${details}</div>` : "");
}
