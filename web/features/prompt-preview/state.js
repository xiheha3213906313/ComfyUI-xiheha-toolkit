// Pure persisted-state and row-context logic for XH_PromptPreview.
export const PREVIEW_CONTEXTS_KEY = "__xh_contexts";

export function promptTokens(value) {
    return String(value ?? "")
        .split(/[,，]/)
        .map((item) => item.replace(/\s+/g, " ").trim())
        .filter(Boolean);
}

export function previewContextId(row) {
    if (typeof row?.context_id === "string" && row.context_id) return row.context_id;
    const sourceName = String(row?.source_name || "").trim();
    const configIndex = Number(row?.config_index);
    if (!sourceName || !Number.isInteger(configIndex)) return "";
    return JSON.stringify([sourceName, configIndex]);
}

function legacyPreviewTokenKey(row, side, index) {
    const modelName = row?.model_name || row?.display_name || row?.source_name || "";
    return `${String(modelName).trim()}|${side}|${index}`;
}

export function previewTokenKey(row, side, index) {
    const contextId = previewContextId(row);
    return contextId
        ? JSON.stringify([contextId, side, Number(index)])
        : legacyPreviewTokenKey(row, side, index);
}

export function syncPreviewTokenState(state, rows) {
    const next = state && typeof state === "object" && !Array.isArray(state) ? { ...state } : {};
    const contexts = [];
    for (const row of rows || []) {
        const contextId = previewContextId(row);
        contexts.push(contextId || null);
        if (!contextId) continue;
        for (const side of ["positive", "negative"]) {
            const tokens = row?.[`${side}_tokens`] || [];
            for (const [index] of tokens.entries()) {
                const legacyKey = legacyPreviewTokenKey(row, side, index);
                const scopedKey = previewTokenKey(row, side, index);
                if (Object.prototype.hasOwnProperty.call(next, legacyKey)) {
                    if (!Object.prototype.hasOwnProperty.call(next, scopedKey)) next[scopedKey] = next[legacyKey];
                    delete next[legacyKey];
                }
            }
        }
    }
    next[PREVIEW_CONTEXTS_KEY] = contexts;
    return next;
}

export function isPreviewTokenEnabled(state, row, side, index) {
    const key = previewTokenKey(row, side, index);
    if (Object.prototype.hasOwnProperty.call(state || {}, key)) return state[key] !== false;
    const enabled = row?.[`${side}_enabled`];
    return !Array.isArray(enabled) || enabled[index] !== false;
}

export function rowToPreviewRow(row) {
    const modelName = row.display_name || row.model_name || row.source_name || "";
    const rawConfigIndex = row.config_index;
    const configIndex = rawConfigIndex == null || rawConfigIndex === "" ? null : Number(rawConfigIndex);
    const previewRow = {
        source_name: String(row.source_name || ""),
        config_index: Number.isInteger(configIndex) ? configIndex : null,
        context_id: typeof row.context_id === "string" ? row.context_id : "",
        display_name: modelName,
        model_name: modelName,
        positive_tokens: row.positive_tokens || promptTokens(row.positive),
        negative_tokens: row.negative_tokens || promptTokens(row.negative),
        positive_enabled: Array.isArray(row.positive_enabled) ? row.positive_enabled : null,
        negative_enabled: Array.isArray(row.negative_enabled) ? row.negative_enabled : null,
    };
    previewRow.context_id ||= previewContextId(previewRow);
    return previewRow;
}
