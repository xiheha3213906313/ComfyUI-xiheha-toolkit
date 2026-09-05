// Read-only local endpoint client. No internet calls are ever made.
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
