// Local-only endpoint client. No internet calls are ever made.
import { api } from "../../../scripts/api.js";

export async function inspectSources(sources) {
    const response = await api.fetchApi("/xiheha_toolkit/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources }),
    });
    if (!response.ok) throw new Error(`配置扫描失败 (${response.status})`);
    const payload = await response.json();
    return Array.isArray(payload.sources) ? payload.sources : [];
}

export async function saveSourceConfigs(sources) {
    const response = await api.fetchApi("/xiheha_toolkit/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources }),
    });
    let payload = {};
    try {
        payload = await response.json();
    } catch {
        // Keep the status-based fallback below when a proxy returns non-JSON.
    }
    if (!response.ok) throw new Error(payload?.error || `配置保存失败 (${response.status})`);
    return Array.isArray(payload.sources) ? payload.sources : [];
}
