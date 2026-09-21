// ComfyUI execution UI payload decoding.
export function parseUiPayload(message, key, fallback) {
    const raw = message?.[key];
    if (!Array.isArray(raw) || raw.length === 0) return fallback;
    try {
        const value = typeof raw[0] === "string" ? JSON.parse(raw[0]) : raw[0];
        return value ?? fallback;
    } catch {
        return fallback;
    }
}
