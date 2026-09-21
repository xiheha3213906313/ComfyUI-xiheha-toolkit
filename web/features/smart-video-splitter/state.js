export const MIN_RANGE = 3;
export const MAX_RANGE = 15;
export const MIN_EDGE_GAP = 0.2;

export const DEFAULT_SPLITTER_STATE = Object.freeze({
    split_mode: "fuzzy",
    fuzzy_min: 4,
    target_duration: 5,
    fuzzy_max: 6,
    video: "",
});

export function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
}

export function round1(value) {
    return Math.round(value * 10) / 10;
}

function finite(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

export function normalizeSplitterState(value = {}) {
    const splitMode = value?.split_mode === "exact" ? "exact" : "fuzzy";
    let target = clamp(round1(finite(value?.target_duration, DEFAULT_SPLITTER_STATE.target_duration)), MIN_RANGE, MAX_RANGE);
    let minimum = clamp(round1(finite(value?.fuzzy_min, DEFAULT_SPLITTER_STATE.fuzzy_min)), MIN_RANGE, MAX_RANGE);
    let maximum = clamp(round1(finite(value?.fuzzy_max, DEFAULT_SPLITTER_STATE.fuzzy_max)), MIN_RANGE, MAX_RANGE);
    minimum = Math.min(minimum, target);
    maximum = Math.max(maximum, target);
    if (round1(maximum - minimum) < MIN_EDGE_GAP) {
        const expandedMaximum = round1(minimum + MIN_EDGE_GAP);
        if (expandedMaximum <= MAX_RANGE) maximum = expandedMaximum;
        else minimum = round1(maximum - MIN_EDGE_GAP);
    }
    target = clamp(target, minimum, maximum);
    return {
        split_mode: splitMode,
        fuzzy_min: minimum,
        target_duration: target,
        fuzzy_max: maximum,
        video: typeof value?.video === "string" ? value.video : "",
    };
}

export function parseSplitterState(serialized, fallbackVideo = "") {
    let parsed = {};
    try {
        parsed = JSON.parse(String(serialized || "{}"));
    } catch {
        parsed = {};
    }
    if (!parsed.video && fallbackVideo && fallbackVideo !== "none") parsed.video = String(fallbackVideo);
    return normalizeSplitterState(parsed);
}

export function serializeSplitterState(state) {
    return JSON.stringify(normalizeSplitterState(state));
}

export function setSplitMode(state, mode) {
    return normalizeSplitterState({ ...state, split_mode: mode });
}

export function moveTimelineHandle(state, handle, rawValue) {
    const current = normalizeSplitterState(state);
    const value = clamp(round1(Number(rawValue)), MIN_RANGE, MAX_RANGE);
    if (!Number.isFinite(value)) return current;
    if (current.split_mode === "exact") {
        return handle === "target"
            ? normalizeSplitterState({ ...current, target_duration: value })
            : current;
    }
    if (handle === "min") {
        const maximum = Math.min(current.target_duration, round1(current.fuzzy_max - MIN_EDGE_GAP));
        current.fuzzy_min = clamp(value, MIN_RANGE, maximum);
    }
    if (handle === "target") current.target_duration = clamp(value, current.fuzzy_min, current.fuzzy_max);
    if (handle === "max") {
        const minimum = Math.max(current.target_duration, round1(current.fuzzy_min + MIN_EDGE_GAP));
        current.fuzzy_max = clamp(value, minimum, MAX_RANGE);
    }
    return normalizeSplitterState(current);
}

export function closestTimelineHandle(state, rawValue) {
    const current = normalizeSplitterState(state);
    if (current.split_mode === "exact") return "target";
    const value = clamp(Number(rawValue), MIN_RANGE, MAX_RANGE);
    if (value < current.fuzzy_min) return "min";
    if (value > current.fuzzy_max) return "max";
    return "target";
}

export function timelinePositions(state) {
    const current = normalizeSplitterState(state);
    const percent = (value) => ((value - MIN_RANGE) / (MAX_RANGE - MIN_RANGE)) * 100;
    return {
        minimum: percent(current.fuzzy_min),
        target: percent(current.target_duration),
        maximum: percent(current.fuzzy_max),
    };
}

export function videoViewPath(filename) {
    const clean = String(filename || "").replace(/\\/g, "/");
    const slash = clean.lastIndexOf("/");
    const subfolder = slash >= 0 ? clean.slice(0, slash) : "";
    const baseName = slash >= 0 ? clean.slice(slash + 1) : clean;
    return `/view?filename=${encodeURIComponent(baseName)}&type=input${subfolder ? `&subfolder=${encodeURIComponent(subfolder)}` : ""}`;
}

export function buildSplitPayload(nodeId, filename, state, widgetValues = {}) {
    const current = normalizeSplitterState({ ...state, video: filename });
    return {
        node_id: nodeId,
        filename,
        force_rate: widgetValues.force_rate ?? 0,
        custom_width: widgetValues.custom_width ?? 0,
        custom_height: widgetValues.custom_height ?? 540,
        format: widgetValues.format ?? "AnimatedDiff",
        split_mode: current.split_mode,
        fuzzy_min: current.fuzzy_min,
        target_duration: current.target_duration,
        fuzzy_max: current.fuzzy_max,
        algorithm: widgetValues.algorithm ?? "智能自适应检测（推荐）",
        sensitivity: widgetValues.sensitivity ?? 0.60,
        cut_threshold: widgetValues.cut_threshold ?? 0.55,
        peak_prominence: widgetValues.peak_prominence ?? 0.12,
    };
}
