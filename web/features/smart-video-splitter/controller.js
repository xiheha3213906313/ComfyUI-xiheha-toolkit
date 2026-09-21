import { app } from "../../../../scripts/app.js";
import { enforceNodeMinimumSize, createRoot } from "../../shared/layout.js";
import { createCleanupBag } from "../../shared/lifecycle.js";
import { markDirty } from "../../shared/workflow.js";
import { hideWidget, showWidget, widgetByName } from "../../shared/widgets.js";
import { registerCustomTooltip, unregisterCustomTooltip } from "../../shared/tooltip.js";
import { MIN_HEIGHT, MIN_WIDTH, preserveNodeSize } from "../../nodes/smart-video-splitter-size.js";
import { apiUrl, getSplitStatus, getVideoInfo, splitVideo, uploadVideo } from "./api.js";
import {
    buildSplitPayload, normalizeSplitterState, parseSplitterState, serializeSplitterState,
    usesSceneDetection, videoViewPath,
} from "./state.js";
import { createSplitterView } from "./view.js";

const HIDDEN_WIDGETS = ["splitter_state", "fuzzy_min", "target_duration", "fuzzy_max", "split_mode"];
const DETECTION_WIDGETS = ["algorithm", "sensitivity", "cut_threshold", "peak_prominence"];
const PARAMETER_WIDGETS = [
    "force_rate", "custom_width", "custom_height", "format",
    "algorithm", "sensitivity", "cut_threshold", "peak_prominence",
];

export function resizeNodeToFit(node) {
    if (!node?.setSize) return;
    const next = preserveNodeSize(node.size, node.computeSize?.());
    if (next[0] !== node.size?.[0] || next[1] !== node.size?.[1]) node.setSize(next);
}

function addVideoOption(widget, filename) {
    const values = widget?.options?.values;
    if (Array.isArray(values) && !values.includes(filename)) values.push(filename);
}

function valuesFromWidgets(node) {
    return Object.fromEntries(PARAMETER_WIDGETS.map((name) => [name, widgetByName(node, name)?.value]));
}

export function createSmartVideoSplitterController(node, { customTooltip = false } = {}) {
    if (node.__xhSplitter) return node.__xhSplitter;
    enforceNodeMinimumSize(node, MIN_WIDTH, MIN_HEIGHT);
    const originalComputeSize = node.computeSize;
    node.computeSize = function (out) {
        const size = originalComputeSize ? originalComputeSize.apply(this, arguments) : (out || [MIN_WIDTH, MIN_HEIGHT]);
        size[0] = Math.max(MIN_WIDTH, size[0]);
        size[1] = Math.max(MIN_HEIGHT, size[1]);
        return size;
    };
    resizeNodeToFit(node);

    const stateWidget = widgetByName(node, "splitter_state");
    const videoWidget = widgetByName(node, "video");
    for (const name of HIDDEN_WIDGETS) hideWidget(widgetByName(node, name));
    let controller;
    const root = createRoot("xh-splitter-box");
    const view = createSplitterView({
        onUpload: (file) => controller?.handleUpload(file),
        onCalculate: () => controller?.calculate(),
        onTimelineChange: (state) => controller?.setTimelineState(state),
    });
    root.append(...view.elements);
    const domWidget = node.addDOMWidget("smart_splitter_ui", "smart_splitter_ui", root, {
        serialize: false,
        hideOnZoom: false,
        computeSize: (width) => [Math.max(MIN_WIDTH, width), Math.max(340, root.offsetHeight || 340)],
    });
    domWidget.element = root;

    const callbackCleanups = createCleanupBag();
    let previewSequence = 0;
    let requestSequence = 0;
    let pollTimer = null;
    let pollSequence = 0;
    let statusText = "就绪。请选择视频并点击「计算」开始分段。";

    controller = {
        node,
        root,
        view,
        state: parseSplitterState(stateWidget?.value, videoWidget?.value),
        dirty: false,
        disposed: false,
        renderStatus(message = null) {
            view.status.textContent = message || (this.dirty
                ? "⚠️ 参数已发生变化，请点击「开始计算」重新生成缓存。"
                : statusText);
            view.status.classList.toggle("xh-status-dirty", this.dirty && !message);
        },
        renderTimeline() {
            view.timeline.render(this.state);
        },
        syncState({ notify = true } = {}) {
            this.state = normalizeSplitterState({ ...this.state, video: videoWidget?.value || this.state.video });
            const assignments = {
                fuzzy_min: this.state.fuzzy_min,
                target_duration: this.state.target_duration,
                fuzzy_max: this.state.fuzzy_max,
                split_mode: this.state.split_mode,
                splitter_state: serializeSplitterState(this.state),
            };
            for (const [name, value] of Object.entries(assignments)) {
                const widget = widgetByName(node, name);
                if (!widget) continue;
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }
            if (notify) markDirty(node);
        },
        updateWidgetVisibility({ notify = true } = {}) {
            for (const name of DETECTION_WIDGETS) {
                const widget = widgetByName(node, name);
                if (usesSceneDetection(this.state.split_mode)) showWidget(widget);
                else hideWidget(widget);
            }
            resizeNodeToFit(node);
            if (notify) markDirty(node);
        },
        setTimelineState(state) {
            const modeChanged = this.state.split_mode !== state.split_mode;
            this.state = normalizeSplitterState({ ...state, video: videoWidget?.value || this.state.video });
            this.dirty = true;
            this.renderTimeline();
            if (modeChanged) this.updateWidgetVisibility({ notify: false });
            this.syncState();
            this.renderStatus();
        },
        setMode(mode) {
            this.setTimelineState({ ...this.state, split_mode: mode });
        },
        stopPolling() {
            pollSequence += 1;
            if (pollTimer) clearTimeout(pollTimer);
            pollTimer = null;
        },
        startPolling() {
            this.stopPolling();
            const sequence = pollSequence;
            const poll = async () => {
                try {
                    const task = await getSplitStatus(node.id);
                    if (this.disposed || sequence !== pollSequence) return;
                    if (task.status === "running") this.renderStatus(task.message || "正在计算...");
                } catch { /* progress polling is best effort */ }
                if (!this.disposed && sequence === pollSequence) pollTimer = setTimeout(poll, 600);
            };
            pollTimer = setTimeout(poll, 600);
        },
        async updateVideoPreviewAndInfo(filename) {
            const sequence = ++previewSequence;
            if (!filename || filename === "none") {
                view.video.hidden = true;
                view.video.removeAttribute("src");
                statusText = "未选择视频。";
                this.dirty = false;
                this.renderStatus();
                return;
            }
            view.video.src = apiUrl(videoViewPath(filename));
            view.video.hidden = false;
            view.video.onloadedmetadata = () => { resizeNodeToFit(node); markDirty(node); };
            try {
                const info = await getVideoInfo(filename);
                if (this.disposed || sequence !== previewSequence) return;
                statusText = `已加载: ${info.filename} | 时长: ${info.duration}s | FPS: ${info.fps} | 分辨率: ${info.width}×${info.height} | 总帧数: ${info.frame_count}`;
            } catch {
                if (this.disposed || sequence !== previewSequence) return;
                statusText = `已加载: ${filename}`;
            }
            this.dirty = false;
            this.renderStatus();
        },
        async handleUpload(file) {
            view.uploadButton.disabled = true;
            view.uploadButton.textContent = "上传中...";
            try {
                const result = await uploadVideo(file);
                if (this.disposed) return;
                const filename = result.subfolder ? `${result.subfolder}/${result.name}` : result.name;
                if (videoWidget) {
                    const oldValue = videoWidget.value;
                    addVideoOption(videoWidget, filename);
                    videoWidget.value = filename;
                    videoWidget.callback?.(filename);
                    node.onWidgetChanged?.(videoWidget.name, filename, oldValue, videoWidget);
                }
                this.syncState();
            } catch (error) {
                globalThis.alert?.(`上传失败: ${error.message}`);
            } finally {
                if (!this.disposed) {
                    view.uploadButton.disabled = false;
                    view.uploadButton.textContent = "上传视频";
                }
            }
        },
        async calculate() {
            const filename = videoWidget?.value;
            if (!filename || filename === "none") {
                globalThis.alert?.("请先选择或上传需要分割的视频！");
                return;
            }
            const sequence = ++requestSequence;
            view.calculateButton.disabled = true;
            view.calculateButton.textContent = "计算中...";
            this.renderStatus("正在启动视频分析与切片引擎...");
            this.startPolling();
            try {
                const result = await splitVideo(buildSplitPayload(node.id, filename, this.state, valuesFromWidgets(node)));
                if (this.disposed || sequence !== requestSequence) return;
                const segments = Array.isArray(result.stream?.segments) ? result.stream.segments : [];
                const average = segments.length
                    ? segments.reduce((total, segment) => total + Number(segment.duration || 0), 0) / segments.length
                    : 0;
                statusText = `✅ 分割完成！生成了 ${segments.length} 个视频片段缓存，平均时长 ${average.toFixed(2)}s。`;
                this.dirty = false;
                this.renderStatus();
            } catch (error) {
                if (!this.disposed && sequence === requestSequence) {
                    statusText = `❌ 计算失败: ${error.message}`;
                    this.renderStatus();
                }
            } finally {
                if (sequence === requestSequence) this.stopPolling();
                if (!this.disposed && sequence === requestSequence) {
                    view.calculateButton.disabled = false;
                    view.calculateButton.textContent = "开始计算";
                    markDirty(node);
                }
            }
        },
        restoreFromWidgets() {
            this.state = parseSplitterState(stateWidget?.value, videoWidget?.value);
            if (this.state.video && videoWidget) {
                addVideoOption(videoWidget, this.state.video);
                videoWidget.value = this.state.video;
            }
            this.renderTimeline();
            this.updateWidgetVisibility({ notify: false });
            this.syncState({ notify: false });
            this.renderStatus();
            if (this.state.video) this.updateVideoPreviewAndInfo(this.state.video);
        },
        dispose() {
            if (this.disposed) return;
            this.disposed = true;
            previewSequence += 1;
            requestSequence += 1;
            this.stopPolling();
            callbackCleanups.run();
            unregisterCustomTooltip(node);
            view.dispose();
            node.computeSize = originalComputeSize;
        },
    };

    const patchCallback = (widget, handler) => {
        if (!widget) return;
        const original = widget.callback;
        const patched = function (...args) { const result = original?.apply(this, args); handler(...args); return result; };
        widget.callback = patched;
        callbackCleanups.add(() => { if (widget.callback === patched) widget.callback = original; });
    };
    patchCallback(videoWidget, (value) => {
        controller.state.video = typeof value === "string" ? value : "";
        controller.dirty = false;
        controller.updateVideoPreviewAndInfo(value);
        if (!app.configuringGraph) controller.syncState();
    });
    for (const name of PARAMETER_WIDGETS) {
        patchCallback(widgetByName(node, name), () => {
            controller.dirty = true;
            controller.renderStatus();
        });
    }
    registerCustomTooltip(node, { enabled: customTooltip, hoverDelay: 1000 });
    node.__xhSplitter = controller;
    controller.restoreFromWidgets();
    return controller;
}
