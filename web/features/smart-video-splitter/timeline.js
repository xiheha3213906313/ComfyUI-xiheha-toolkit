import {
    MAX_RANGE, MIN_EDGE_GAP, MIN_RANGE, clamp, closestTimelineHandle, moveTimelineHandle, round1,
    setSplitMode, timelinePositions,
} from "./state.js";

function durationFromPointer(track, event) {
    const rect = track.getBoundingClientRect();
    if (rect.width <= 0) return null;
    const x = clamp(event.clientX - rect.left, 0, rect.width);
    return round1(MIN_RANGE + (x / rect.width) * (MAX_RANGE - MIN_RANGE));
}

export function createTimeline({ onChange }) {
    const panel = document.createElement("section");
    panel.className = "xh-timeline-panel";
    const header = document.createElement("div");
    header.className = "xh-timeline-header";
    const heading = document.createElement("div");
    heading.className = "xh-timeline-heading";
    const title = document.createElement("div");
    title.className = "xh-timeline-title";
    title.textContent = "分段时长";
    const unit = document.createElement("span");
    unit.className = "xh-timeline-unit";
    unit.textContent = "秒";
    heading.append(title, unit);
    const modeSwitch = document.createElement("div");
    modeSwitch.className = "xh-seg-switch";
    modeSwitch.setAttribute("role", "group");
    modeSwitch.setAttribute("aria-label", "分段模式");
    const targetTab = document.createElement("button");
    targetTab.className = "xh-seg-item";
    targetTab.type = "button";
    targetTab.textContent = "目标";
    const sceneTab = document.createElement("button");
    sceneTab.className = "xh-seg-item";
    sceneTab.type = "button";
    sceneTab.textContent = "模糊";
    const exactTab = document.createElement("button");
    exactTab.className = "xh-seg-item";
    exactTab.type = "button";
    exactTab.textContent = "精确";
    modeSwitch.append(targetTab, sceneTab, exactTab);
    header.append(heading, modeSwitch);
    panel.appendChild(header);

    const wrap = document.createElement("div");
    wrap.className = "xh-timeline-wrap";
    const track = document.createElement("div");
    track.className = "xh-timeline-track";
    const rail = document.createElement("div");
    rail.className = "xh-timeline-rail";
    const range = document.createElement("div");
    range.className = "xh-timeline-range";
    const ticks = document.createElement("div");
    ticks.className = "xh-timeline-ticks";
    for (let value = MIN_RANGE; value <= MAX_RANGE; value += 1) {
        const tick = document.createElement("span");
        tick.className = "xh-timeline-tick";
        tick.style.left = `${((value - MIN_RANGE) / (MAX_RANGE - MIN_RANGE)) * 100}%`;
        ticks.appendChild(tick);
    }
    const handles = {
        min: document.createElement("div"),
        target: document.createElement("div"),
        max: document.createElement("div"),
    };
    handles.min.className = "xh-handle";
    handles.min.title = "最短时长";
    handles.min.setAttribute("role", "slider");
    handles.min.setAttribute("tabindex", "0");
    handles.min.setAttribute("aria-label", "最短时长");
    handles.target.className = "xh-handle-target";
    handles.target.title = "目标时长";
    handles.target.setAttribute("role", "slider");
    handles.target.setAttribute("tabindex", "0");
    handles.target.setAttribute("aria-label", "目标时长");
    handles.max.className = "xh-handle";
    handles.max.title = "最长时长";
    handles.max.setAttribute("role", "slider");
    handles.max.setAttribute("tabindex", "0");
    handles.max.setAttribute("aria-label", "最长时长");
    rail.append(range, ticks);
    track.append(rail, handles.min, handles.target, handles.max);
    wrap.appendChild(track);
    panel.appendChild(wrap);
    const labels = document.createElement("div");
    labels.className = "xh-timeline-labels";
    panel.appendChild(labels);

    let state = null;
    let activeHandle = null;
    let activePointerId = null;
    const emitMove = (handle, value) => {
        state = moveTimelineHandle(state, handle, value);
        onChange(state);
    };
    const onPointerMove = (event) => {
        if (!activeHandle || (activePointerId != null && event.pointerId !== activePointerId)) return;
        const value = durationFromPointer(track, event);
        if (value != null) emitMove(activeHandle, value);
    };
    const onVisibilityChange = () => {
        if (document.hidden) stopDragging();
    };
    const stopDragging = (event = null) => {
        if (event?.pointerId != null && activePointerId != null && event.pointerId !== activePointerId) return;
        const pointerId = activePointerId;
        if (activeHandle) handles[activeHandle].classList.remove("dragging");
        activeHandle = null;
        activePointerId = null;
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", stopDragging, true);
        document.removeEventListener("pointercancel", stopDragging, true);
        window.removeEventListener("blur", stopDragging);
        document.removeEventListener("visibilitychange", onVisibilityChange);
        if (pointerId != null && track.hasPointerCapture?.(pointerId)) {
            track.releasePointerCapture(pointerId);
        }
    };
    const startDragging = (event, handle) => {
        event.preventDefault();
        event.stopPropagation();
        stopDragging();
        activeHandle = handle;
        activePointerId = event.pointerId;
        handles[handle].classList.add("dragging");
        track.setPointerCapture?.(event.pointerId);
        document.addEventListener("pointermove", onPointerMove);
        document.addEventListener("pointerup", stopDragging, true);
        document.addEventListener("pointercancel", stopDragging, true);
        window.addEventListener("blur", stopDragging);
        document.addEventListener("visibilitychange", onVisibilityChange);
    };
    track.addEventListener("lostpointercapture", stopDragging);
    for (const [name, handle] of Object.entries(handles)) {
        handle.addEventListener("pointerdown", (event) => startDragging(event, name));
        handle.addEventListener("keydown", (event) => {
            const value = name === "min" ? state.fuzzy_min
                : name === "max" ? state.fuzzy_max
                    : state.target_duration;
            const step = event.shiftKey ? 1 : 0.1;
            let nextValue = null;
            if (event.key === "ArrowLeft" || event.key === "ArrowDown") nextValue = value - step;
            if (event.key === "ArrowRight" || event.key === "ArrowUp") nextValue = value + step;
            if (event.key === "Home") nextValue = MIN_RANGE;
            if (event.key === "End") nextValue = MAX_RANGE;
            if (nextValue == null) return;
            event.preventDefault();
            event.stopPropagation();
            emitMove(name, nextValue);
        });
    }
    targetTab.addEventListener("click", () => onChange(setSplitMode(state, "fuzzy")));
    sceneTab.addEventListener("click", () => onChange(setSplitMode(state, "scene")));
    exactTab.addEventListener("click", () => onChange(setSplitMode(state, "exact")));
    track.addEventListener("pointerdown", (event) => {
        if (event.target !== track && event.target !== rail && event.target !== range) return;
        const value = durationFromPointer(track, event);
        if (value == null) return;
        const handle = closestTimelineHandle(state, value);
        startDragging(event, handle);
        emitMove(handle, value);
    });

    function render(nextState) {
        state = nextState;
        const positions = timelinePositions(state);
        const targetMode = state.split_mode === "fuzzy";
        const sceneMode = state.split_mode === "scene";
        const exactMode = state.split_mode === "exact";
        const rangedMode = targetMode || sceneMode;
        panel.classList.toggle("is-exact", exactMode);
        targetTab.classList.toggle("active", targetMode);
        sceneTab.classList.toggle("active", sceneMode);
        exactTab.classList.toggle("active", exactMode);
        targetTab.setAttribute("aria-pressed", String(targetMode));
        sceneTab.setAttribute("aria-pressed", String(sceneMode));
        exactTab.setAttribute("aria-pressed", String(exactMode));
        handles.min.style.display = rangedMode ? "block" : "none";
        handles.target.style.display = sceneMode ? "none" : "block";
        handles.max.style.display = rangedMode ? "block" : "none";
        range.style.display = "block";
        handles.min.style.left = `${positions.minimum}%`;
        handles.target.style.left = `${positions.target}%`;
        handles.max.style.left = `${positions.maximum}%`;
        range.style.left = rangedMode ? `${positions.minimum}%` : "0";
        range.style.width = rangedMode
            ? `${Math.max(0, positions.maximum - positions.minimum)}%`
            : `${positions.target}%`;
        const values = {
            min: state.fuzzy_min,
            target: state.target_duration,
            max: state.fuzzy_max,
        };
        for (const [name, handle] of Object.entries(handles)) {
            let minimum = MIN_RANGE;
            let maximum = MAX_RANGE;
            if (sceneMode && name === "min") maximum = round1(state.fuzzy_max - MIN_EDGE_GAP);
            if (sceneMode && name === "max") minimum = round1(state.fuzzy_min + MIN_EDGE_GAP);
            if (targetMode && name === "min") {
                maximum = Math.min(state.target_duration, round1(state.fuzzy_max - MIN_EDGE_GAP));
            }
            if (targetMode && name === "target") {
                minimum = state.fuzzy_min;
                maximum = state.fuzzy_max;
            }
            if (targetMode && name === "max") {
                minimum = Math.max(state.target_duration, round1(state.fuzzy_min + MIN_EDGE_GAP));
            }
            handle.setAttribute("aria-valuemin", String(minimum));
            handle.setAttribute("aria-valuemax", String(maximum));
            handle.setAttribute("aria-valuenow", values[name].toFixed(1));
            handle.setAttribute("aria-valuetext", `${values[name].toFixed(1)} 秒`);
        }
        labels.textContent = "";
        if (targetMode) {
            for (const [label, value] of [["最短", state.fuzzy_min], ["目标", state.target_duration], ["最长", state.fuzzy_max]]) {
                const stat = document.createElement("span");
                stat.append(`${label}: `);
                const bold = document.createElement("b");
                bold.textContent = `${value.toFixed(1)}s`;
                stat.appendChild(bold);
                labels.appendChild(stat);
            }
        } else if (sceneMode) {
            for (const [label, value] of [["最短", state.fuzzy_min], ["最长", state.fuzzy_max]]) {
                const stat = document.createElement("span");
                stat.append(`${label}: `);
                const bold = document.createElement("b");
                bold.textContent = `${value.toFixed(1)}s`;
                stat.appendChild(bold);
                labels.appendChild(stat);
            }
        } else {
            const minimum = document.createElement("span");
            minimum.className = "xh-timeline-boundary";
            minimum.textContent = `${MIN_RANGE.toFixed(1)}s`;
            const target = document.createElement("span");
            target.append("目标时长: ");
            const bold = document.createElement("b");
            bold.textContent = `${state.target_duration.toFixed(1)}s`;
            target.append(bold, " (固定切分)");
            const maximum = document.createElement("span");
            maximum.className = "xh-timeline-boundary";
            maximum.textContent = `${MAX_RANGE.toFixed(1)}s`;
            labels.append(minimum, target, maximum);
        }
    }
    return {
        element: panel,
        render,
        dispose() {
            stopDragging();
            track.removeEventListener("lostpointercapture", stopDragging);
        },
    };
}
