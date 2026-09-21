import {
    MAX_RANGE, MIN_RANGE, clamp, closestTimelineHandle, moveTimelineHandle, round1,
    setSplitMode, timelinePositions,
} from "./state.js";

function durationFromPointer(track, event) {
    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return null;
    const x = clamp(event.clientX - rect.left, 0, rect.width);
    return round1(MIN_RANGE + (x / rect.width) * (MAX_RANGE - MIN_RANGE));
}

export function createTimeline({ onChange }) {
    const fragment = document.createDocumentFragment();
    const header = document.createElement("div");
    header.className = "xh-timeline-header";
    const title = document.createElement("div");
    title.className = "xh-timeline-title";
    title.textContent = "分段时长 (秒)";
    const modeSwitch = document.createElement("div");
    modeSwitch.className = "xh-seg-switch";
    const fuzzyTab = document.createElement("div");
    fuzzyTab.className = "xh-seg-item";
    fuzzyTab.textContent = "模糊";
    const exactTab = document.createElement("div");
    exactTab.className = "xh-seg-item";
    exactTab.textContent = "精确";
    modeSwitch.append(fuzzyTab, exactTab);
    header.append(title, modeSwitch);
    fragment.appendChild(header);

    const wrap = document.createElement("div");
    wrap.className = "xh-timeline-wrap";
    const track = document.createElement("div");
    track.className = "xh-timeline-track";
    const range = document.createElement("div");
    range.className = "xh-timeline-range";
    const handles = {
        min: document.createElement("div"),
        target: document.createElement("div"),
        max: document.createElement("div"),
    };
    handles.min.className = "xh-handle";
    handles.min.title = "最短时长";
    handles.target.className = "xh-handle-target";
    handles.target.title = "目标时长";
    handles.max.className = "xh-handle";
    handles.max.title = "最长时长";
    track.append(range, handles.min, handles.target, handles.max);
    wrap.appendChild(track);
    fragment.appendChild(wrap);
    const labels = document.createElement("div");
    labels.className = "xh-timeline-labels";
    fragment.appendChild(labels);

    let state = null;
    let activeHandle = null;
    const emitMove = (handle, value) => {
        state = moveTimelineHandle(state, handle, value);
        onChange(state);
    };
    const onPointerMove = (event) => {
        if (!activeHandle) return;
        const value = durationFromPointer(track, event);
        if (value != null) emitMove(activeHandle, value);
    };
    const stopDragging = () => {
        activeHandle = null;
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", stopDragging);
        document.removeEventListener("pointercancel", stopDragging);
    };
    const startDragging = (event, handle) => {
        event.preventDefault();
        event.stopPropagation();
        stopDragging();
        activeHandle = handle;
        document.addEventListener("pointermove", onPointerMove);
        document.addEventListener("pointerup", stopDragging);
        document.addEventListener("pointercancel", stopDragging);
    };
    for (const [name, handle] of Object.entries(handles)) {
        handle.addEventListener("pointerdown", (event) => startDragging(event, name));
    }
    fuzzyTab.addEventListener("click", () => onChange(setSplitMode(state, "fuzzy")));
    exactTab.addEventListener("click", () => onChange(setSplitMode(state, "exact")));
    track.addEventListener("pointerdown", (event) => {
        if (event.target !== track && event.target !== range) return;
        const value = durationFromPointer(track, event);
        if (value != null) emitMove(closestTimelineHandle(state, value), value);
    });

    function render(nextState) {
        state = nextState;
        const positions = timelinePositions(state);
        const fuzzy = state.split_mode === "fuzzy";
        fuzzyTab.classList.toggle("active", fuzzy);
        exactTab.classList.toggle("active", !fuzzy);
        handles.min.style.display = fuzzy ? "block" : "none";
        handles.max.style.display = fuzzy ? "block" : "none";
        range.style.display = fuzzy ? "block" : "none";
        handles.min.style.left = `${positions.minimum}%`;
        handles.target.style.left = `${positions.target}%`;
        handles.max.style.left = `${positions.maximum}%`;
        range.style.left = `${positions.minimum}%`;
        range.style.width = `${Math.max(0, positions.maximum - positions.minimum)}%`;
        labels.textContent = "";
        if (fuzzy) {
            for (const [label, value] of [["最短", state.fuzzy_min], ["目标", state.target_duration], ["最长", state.fuzzy_max]]) {
                const span = document.createElement("span");
                span.append(`${label}: `);
                const bold = document.createElement("b");
                bold.textContent = `${value.toFixed(1)}s`;
                span.appendChild(bold);
                labels.appendChild(span);
            }
        } else {
            const minimum = document.createElement("span");
            minimum.style.color = "#718096";
            minimum.textContent = "3.0s";
            const target = document.createElement("span");
            target.append("目标时长: ");
            const bold = document.createElement("b");
            bold.textContent = `${state.target_duration.toFixed(1)}s`;
            target.append(bold, " (固定切分)");
            const maximum = document.createElement("span");
            maximum.style.color = "#718096";
            maximum.textContent = "15.0s";
            labels.append(minimum, target, maximum);
        }
    }
    return { element: fragment, render, dispose: stopDragging };
}
