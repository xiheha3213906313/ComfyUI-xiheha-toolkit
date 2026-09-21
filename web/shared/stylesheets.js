// Idempotent local stylesheet loading for the extension.
const installed = new Set();

export function ensureStylesheet(id, href, documentRef = globalThis.document) {
    if (!documentRef || installed.has(id)) return;
    if (documentRef.getElementById(id)) {
        installed.add(id);
        return;
    }
    const link = documentRef.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    documentRef.head.appendChild(link);
    installed.add(id);
}

export function ensureToolkitStylesheet(documentRef = globalThis.document) {
    ensureStylesheet("xh-toolkit-stylesheet", new URL("../toolkit.css", import.meta.url).href, documentRef);
}

export function ensureTooltipStylesheet(documentRef = globalThis.document) {
    ensureStylesheet("xh-tooltip-stylesheet", new URL("../styles/tooltip.css", import.meta.url).href, documentRef);
}
