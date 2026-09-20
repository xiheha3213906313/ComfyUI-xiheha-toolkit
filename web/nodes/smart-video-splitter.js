// XH_SmartVideoSplitter frontend controller and UI components.
import { api } from "../../../scripts/api.js";
import { app } from "../../../scripts/app.js";
import { SMART_SPLITTER_NODE } from "../shared/constants.js";
import { MIN_HEIGHT, MIN_WIDTH, preserveNodeSize } from "./smart-video-splitter-size.js";
import {
    applyPortLabels,
    createRoot,
    enforceNodeMinimumSize,
    hideWidget,
    markDirty,
    showWidget,
    widgetByName,
} from "../shared/dom.js";
import {
    registerCustomTooltip,
    unregisterCustomTooltip,
    updateTooltipMutualExclusion,
    showTooltip as sharedShowTooltip,
    hideTooltip as sharedHideTooltip,
    getWidgetAtPos as sharedGetWidgetAtPos,
    ensureGlobalListeners,
    ensureTooltipStylesheet,
} from "../shared/tooltip.js";

export const NODE_ID = SMART_SPLITTER_NODE;
export { MIN_HEIGHT, MIN_WIDTH } from "./smart-video-splitter-size.js";

const MIN_RANGE = 3.0;
const MAX_RANGE = 15.0;

function clamp(val, min, max) {
    return Math.max(min, Math.min(max, val));
}

function round1(val) {
    return Math.round(val * 10) / 10;
}

// 备用开关：设为 true 时激活高质感毛玻璃定制悬浮卡片；设为 false 时使用 ComfyUI 原生 Tooltip
export const ENABLE_CUSTOM_TOOLTIP = false;

export const WIDGET_TOOLTIPS = {
    format: {
        title: "模型格式",
        enName: "format",
        badge: "模型对齐约束",
        desc: "选择目标视频生成模型生态的规格标准。系统会根据所选格式的算法特征，自动计算对齐倍数（如 8x/16x/32x）与比例要求，对视频片段进行等比缩放与智能裁切。",
        details: [
            "<b>AnimatedDiff</b>：标准 8 像素对齐，兼顾通用 SD1.5 / SDXL 动图工作流",
            "<b>Mochi</b>：16 像素降采样对齐，适配大模型空间注意力机制",
            "<b>LTX-Video</b>：32 像素重采样对齐，支持极高空间压缩比",
            "<b>Wan (万相)</b>：Wan2.1 系列特化编码与补帧适配",
            "<b>原尺寸/自定义</b>：保持原始宽高比或严格按填写的自定义宽高输出",
        ],
    },
    algorithm: {
        title: "检测算法",
        enName: "algorithm",
        badge: "镜头转场核心",
        desc: "用于自动识别视频中镜头切换、场景跳切与转场突变的核心比对算法。",
        details: [
            "<b>智能混合检测（推荐）</b>：结合 HSV 色相直方图与 Content 纹理亮度的自适应双轨检测，抗晃动噪点，切镜准确率最高",
            "<b>Content 内容变化</b>：基于亮度差与边缘纹理突变检测硬切，对光影闪变敏感",
            "<b>HSV 直方图</b>：分析色相、饱和度与明度分布，适合捕获色调反差或色彩风格剧变",
            "<b>SSIM 结构变化</b>：计算画面结构相似性衰减，擅长检测大幅构图重组",
            "<b>Frame Difference 帧差</b>：逐像素绝对差值统计，运算速度极快，适合平缓视频",
            "<b>Perceptual Hash 感知哈希</b>：基于频域指纹比对宏观视觉特征，对微小运动鲁棒",
        ],
    },
    sensitivity: {
        title: "检测灵敏度",
        enName: "sensitivity",
        badge: "动态容差调节",
        desc: "控制镜头突变判定的全局容差。默认值 <b>0.60</b>（范围 0.00 ~ 1.00）。",
        details: [
            "<b>数值越高（如 0.70 ~ 0.90）</b>：更敏锐，微小的运镜晃动、快速摇移或短促跳切均会被切分，片段更碎",
            "<b>数值越低（如 0.30 ~ 0.50）</b>：更保守，仅在发生彻底、明显的场景转变时才切分，避免过度切碎",
        ],
    },
    cut_threshold: {
        title: "切镜阈值",
        enName: "cut_threshold",
        badge: "硬性突变门槛",
        desc: "判定两帧之间发生镜头突变的最低绝对分数门槛。默认值 <b>0.55</b>（范围 0.00 ~ 1.00）。",
        details: [
            "<b>数值越高（如 0.70+）</b>：要求极其强烈的视觉反差（如黑屏过渡、不同场景硬切），减少切片数量",
            "<b>数值越低（如 0.35 ~ 0.45）</b>：对同机位微小转场、淡入淡出更易识别，保留更多细微切点",
        ],
    },
    peak_prominence: {
        title: "显著度阈值",
        enName: "peak_prominence",
        badge: "晃动噪点抑制",
        desc: "局部切镜突变峰值与相邻两帧背景基准线的最小落差要求。默认值 <b>0.12</b>（范围 0.00 ~ 1.00）。",
        details: [
            "<b>核心作用</b>：有效过滤手持跟拍晃动、镜头快速推拉摇移（Pan/Zoom）引起的连续高分误判",
            "<b>调高数值</b>：消除连续运镜造成的假转场，只在出现孤立显著突变时落刀",
            "<b>调低数值</b>：保留密集快切、快节奏蒙太奇等紧凑切镜点",
        ],
    },
    video: {
        title: "视频源文件",
        enName: "video",
        badge: "输入素材",
        desc: "选择已放置在 ComfyUI input 目录中的视频，或点击下方「上传视频」按钮直接上传本地视频。",
        details: [],
    },
    force_rate: {
        title: "强制帧率",
        enName: "force_rate",
        badge: "FPS 重采样",
        desc: "强制将提取的视频片段重采样为指定帧率（FPS）。设为 <b>0</b> 时保持源视频原始帧率不变。",
        details: [],
    },
    custom_width: {
        title: "自定义宽度",
        enName: "custom_width",
        badge: "空间分辨率",
        desc: "输出视频片段的目标宽度（像素）。设为 <b>0</b> 时根据高度与源视频比例自动换算，并满足模型倍数对齐。",
        details: [],
    },
    custom_height: {
        title: "自定义高度",
        enName: "custom_height",
        badge: "空间分辨率",
        desc: "输出视频片段的目标高度（像素，默认 540）。若宽高均设为 0，则直接保持源视频原始尺寸。",
        details: [],
    },
};

export const hideTooltip = sharedHideTooltip;
export const getWidgetAtPos = sharedGetWidgetAtPos;

export function showTooltip(nameOrData, clientX, clientY) {
    if (typeof nameOrData === "string") {
        const data = WIDGET_TOOLTIPS[nameOrData];
        if (data) sharedShowTooltip(data, clientX, clientY);
    } else if (nameOrData) {
        sharedShowTooltip(nameOrData, clientX, clientY);
    }
}

export function setupWidgetTooltips() {
    if (ENABLE_CUSTOM_TOOLTIP) {
        ensureTooltipStylesheet();
        ensureGlobalListeners();
    }
}

function resizeNodeToFit(node) {
    if (!node?.setSize) return;
    const nextSize = preserveNodeSize(node.size, node.computeSize?.());
    if (nextSize[0] !== node.size?.[0] || nextSize[1] !== node.size?.[1]) {
        node.setSize(nextSize);
    }
}

// 自动互斥处理：严格限制在当前智能视频分割器节点实例内，绝不触碰或影响其它任何节点
export function applyTooltipMutualExclusion(node) {
    if (!node || !node.widgets) return;
    registerCustomTooltip(node, {
        enabled: ENABLE_CUSTOM_TOOLTIP,
        hoverDelay: 1000,
        tooltips: WIDGET_TOOLTIPS,
    });
    for (const w of node.widgets) {
        // 严格白名单过滤：只处理属于本分割器的控件
        if (!w || !WIDGET_TOOLTIPS[w.name]) continue;

        if (ENABLE_CUSTOM_TOOLTIP) {
            // 开启定制卡片时：自动清空控件上的 widget.tooltip（暂存起来），屏蔽官方原生浮窗，防止双浮窗冲突
            if (w.tooltip) {
                w.__origTooltip = w.tooltip;
                w.tooltip = null;
            }
        } else {
            // 关闭定制卡片时：恢复 widget.tooltip，由官方原生浮窗展示
            if (w.__origTooltip) {
                w.tooltip = w.__origTooltip;
            }
        }
    }
}

export function splitterController(node) {
    if (node.__xhSplitter) return node.__xhSplitter;

    enforceNodeMinimumSize(node, MIN_WIDTH, MIN_HEIGHT);

    const origComputeSize = node.computeSize;
    node.computeSize = function (out) {
        const res = origComputeSize ? origComputeSize.apply(this, arguments) : (out || [MIN_WIDTH, MIN_HEIGHT]);
        res[0] = Math.max(MIN_WIDTH, res[0]);
        res[1] = Math.max(MIN_HEIGHT, res[1]);
        return res;
    };

    resizeNodeToFit(node);

    let splitMode = "fuzzy";
    let fuzzyMin = 4.0;
    let targetDuration = 5.0;
    let fuzzyMax = 6.0;
    let isDirty = false;
    let statusText = "就绪。请选择视频并点击「计算」开始分段。";

    const root = createRoot("xh-splitter-box");

    // 1. Horizontal Action Buttons: [ 上传 ] [ 计算 ]
    const actionBar = document.createElement("div");
    actionBar.className = "xh-action-bar";

    const uploadBtn = document.createElement("button");
    uploadBtn.className = "xh-action-btn";
    uploadBtn.type = "button";
    uploadBtn.textContent = "上传视频";

    const calcBtn = document.createElement("button");
    calcBtn.className = "xh-action-btn primary";
    calcBtn.type = "button";
    calcBtn.textContent = "开始计算";

    actionBar.appendChild(uploadBtn);
    actionBar.appendChild(calcBtn);
    root.appendChild(actionBar);

    // File input for upload
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "video/mp4,video/webm,video/x-matroska,video/quicktime,video/avi,image/gif";
    fileInput.style.display = "none";
    document.body.appendChild(fileInput);

    // 2. Timeline Section Header: 分段时长 + [ 模糊 | 精确 ] Switch
    const timelineHeader = document.createElement("div");
    timelineHeader.className = "xh-timeline-header";

    const timelineTitle = document.createElement("div");
    timelineTitle.className = "xh-timeline-title";
    timelineTitle.textContent = "分段时长 (秒)";

    const segSwitch = document.createElement("div");
    segSwitch.className = "xh-seg-switch";

    const fuzzyTab = document.createElement("div");
    fuzzyTab.className = "xh-seg-item active";
    fuzzyTab.textContent = "模糊";

    const exactTab = document.createElement("div");
    exactTab.className = "xh-seg-item";
    exactTab.textContent = "精确";

    segSwitch.appendChild(fuzzyTab);
    segSwitch.appendChild(exactTab);
    timelineHeader.appendChild(timelineTitle);
    timelineHeader.appendChild(segSwitch);
    root.appendChild(timelineHeader);

    // 3. Interactive Slider Timeline
    const timelineWrap = document.createElement("div");
    timelineWrap.className = "xh-timeline-wrap";

    const track = document.createElement("div");
    track.className = "xh-timeline-track";

    const rangeHighlight = document.createElement("div");
    rangeHighlight.className = "xh-timeline-range";

    const handleMin = document.createElement("div");
    handleMin.className = "xh-handle";
    handleMin.title = "最短时长";

    const handleTarget = document.createElement("div");
    handleTarget.className = "xh-handle-target";
    handleTarget.title = "目标时长";

    const handleMax = document.createElement("div");
    handleMax.className = "xh-handle";
    handleMax.title = "最长时长";

    track.appendChild(rangeHighlight);
    track.appendChild(handleMin);
    track.appendChild(handleTarget);
    track.appendChild(handleMax);
    timelineWrap.appendChild(track);
    root.appendChild(timelineWrap);

    // Subtitle labels under timeline
    const timelineLabels = document.createElement("div");
    timelineLabels.className = "xh-timeline-labels";
    root.appendChild(timelineLabels);

    // 4. Video Preview Container
    const previewContainer = document.createElement("div");
    previewContainer.className = "xh-preview-container";

    const videoEl = document.createElement("video");
    videoEl.className = "xh-preview-video";
    videoEl.controls = true;
    videoEl.loop = true;
    videoEl.muted = true;
    videoEl.playsInline = true;
    videoEl.hidden = true;
    previewContainer.appendChild(videoEl);
    root.appendChild(previewContainer);

    // 5. Status Information Panel
    const statusPanel = document.createElement("div");
    statusPanel.className = "xh-status-panel";
    statusPanel.textContent = statusText;
    root.appendChild(statusPanel);

    // Hide internal widgets replaced by custom UI
    const stateWidget = widgetByName(node, "splitter_state");
    const fuzzyMinWidget = widgetByName(node, "fuzzy_min");
    const targetDurationWidget = widgetByName(node, "target_duration");
    const fuzzyMaxWidget = widgetByName(node, "fuzzy_max");
    const splitModeWidget = widgetByName(node, "split_mode");

    hideWidget(stateWidget);
    hideWidget(fuzzyMinWidget);
    hideWidget(targetDurationWidget);
    hideWidget(fuzzyMaxWidget);
    hideWidget(splitModeWidget);

    const WIDGET_LABELS = {
        video: "视频",
        force_rate: "强制帧率",
        custom_width: "自定义宽度",
        custom_height: "自定义高度",
        format: "模型格式",
        algorithm: "检测算法",
        sensitivity: "检测灵敏度",
        cut_threshold: "切镜阈值",
        peak_prominence: "显著度阈值",
    };

    for (const [name, label] of Object.entries(WIDGET_LABELS)) {
        const w = widgetByName(node, name);
        if (w) w.label = label;
    }
    applyTooltipMutualExclusion(node);

    // Detection widgets that toggle visibility
    const detectionWidgetNames = ["algorithm", "sensitivity", "cut_threshold", "peak_prominence"];

    function updateWidgetVisibility() {
        const isFuzzy = splitMode === "fuzzy";
        for (const name of detectionWidgetNames) {
            const w = widgetByName(node, name);
            if (!w) continue;
            if (isFuzzy) {
                showWidget(w);
                if (WIDGET_LABELS[name]) w.label = WIDGET_LABELS[name];
            } else {
                hideWidget(w);
            }
        }
        applyTooltipMutualExclusion(node);
        resizeNodeToFit(node);
        markDirty(node);
    }

    function syncStateToWidgets() {
        if (fuzzyMinWidget) fuzzyMinWidget.value = fuzzyMin;
        if (targetDurationWidget) targetDurationWidget.value = targetDuration;
        if (fuzzyMaxWidget) fuzzyMaxWidget.value = fuzzyMax;
        if (splitModeWidget) splitModeWidget.value = splitMode;

        if (stateWidget) {
            stateWidget.value = JSON.stringify({
                split_mode: splitMode,
                fuzzy_min: fuzzyMin,
                target_duration: targetDuration,
                fuzzy_max: fuzzyMax,
            });
        }
    }

    function updateTimelinePositions() {
        const span = MAX_RANGE - MIN_RANGE;
        const minPct = ((fuzzyMin - MIN_RANGE) / span) * 100;
        const targetPct = ((targetDuration - MIN_RANGE) / span) * 100;
        const maxPct = ((fuzzyMax - MIN_RANGE) / span) * 100;

        if (splitMode === "fuzzy") {
            handleMin.style.display = "block";
            handleMax.style.display = "block";
            rangeHighlight.style.display = "block";

            handleMin.style.left = `${minPct}%`;
            handleTarget.style.left = `${targetPct}%`;
            handleMax.style.left = `${maxPct}%`;

            rangeHighlight.style.left = `${minPct}%`;
            rangeHighlight.style.width = `${Math.max(0, maxPct - minPct)}%`;

            timelineLabels.innerHTML = `<span>最短: <b>${fuzzyMin.toFixed(1)}s</b></span><span>目标: <b>${targetDuration.toFixed(1)}s</b></span><span>最长: <b>${fuzzyMax.toFixed(1)}s</b></span>`;
        } else {
            handleMin.style.display = "none";
            handleMax.style.display = "none";
            rangeHighlight.style.display = "none";

            handleTarget.style.left = `${targetPct}%`;
            timelineLabels.innerHTML = `<span style="color:#718096">3.0s</span><span>目标时长: <b>${targetDuration.toFixed(1)}s</b> (固定切分)</span><span style="color:#718096">15.0s</span>`;
        }
    }

    function setMode(mode) {
        if (splitMode === mode) return;
        splitMode = mode;
        if (splitMode === "fuzzy") {
            fuzzyTab.classList.add("active");
            exactTab.classList.remove("active");
            // Auto clamp boundaries: MIN <= TARGET <= MAX
            fuzzyMin = Math.min(fuzzyMin, targetDuration);
            fuzzyMax = Math.max(fuzzyMax, targetDuration);
        } else {
            fuzzyTab.classList.remove("active");
            exactTab.classList.add("active");
        }
        updateTimelinePositions();
        updateWidgetVisibility();
        syncStateToWidgets();
        markDirty(node);
    }

    fuzzyTab.addEventListener("click", () => setMode("fuzzy"));
    exactTab.addEventListener("click", () => setMode("exact"));

    // Dragging Timeline Handles
    let activeDragHandle = null;

    function onPointerDown(e, handleType) {
        e.preventDefault();
        e.stopPropagation();
        activeDragHandle = handleType;
        document.addEventListener("pointermove", onPointerMove);
        document.addEventListener("pointerup", onPointerUp);
    }

    function onPointerMove(e) {
        if (!activeDragHandle) return;
        const rect = track.getBoundingClientRect();
        if (rect.width <= 0) return;
        const x = clamp(e.clientX - rect.left, 0, rect.width);
        const val = round1(MIN_RANGE + (x / rect.width) * (MAX_RANGE - MIN_RANGE));

        if (splitMode === "fuzzy") {
            if (activeDragHandle === "min") {
                fuzzyMin = clamp(val, MIN_RANGE, targetDuration);
            } else if (activeDragHandle === "max") {
                fuzzyMax = clamp(val, targetDuration, MAX_RANGE);
            } else if (activeDragHandle === "target") {
                targetDuration = clamp(val, fuzzyMin, fuzzyMax);
            }
        } else {
            if (activeDragHandle === "target") {
                targetDuration = clamp(val, MIN_RANGE, MAX_RANGE);
            }
        }

        isDirty = true;
        updateTimelinePositions();
        syncStateToWidgets();
        updateStatus();
    }

    function onPointerUp() {
        activeDragHandle = null;
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", onPointerUp);
    }

    handleMin.addEventListener("pointerdown", (e) => onPointerDown(e, "min"));
    handleTarget.addEventListener("pointerdown", (e) => onPointerDown(e, "target"));
    handleMax.addEventListener("pointerdown", (e) => onPointerDown(e, "max"));

    track.addEventListener("pointerdown", (e) => {
        if (e.target !== track && e.target !== rangeHighlight) return;
        const rect = track.getBoundingClientRect();
        const x = clamp(e.clientX - rect.left, 0, rect.width);
        const val = round1(MIN_RANGE + (x / rect.width) * (MAX_RANGE - MIN_RANGE));

        if (splitMode === "exact") {
            targetDuration = clamp(val, MIN_RANGE, MAX_RANGE);
        } else {
            // Find closest cursor to move
            const dMin = Math.abs(val - fuzzyMin);
            const dTarget = Math.abs(val - targetDuration);
            const dMax = Math.abs(val - fuzzyMax);
            if (dMin <= dTarget && dMin <= dMax && val <= targetDuration) {
                fuzzyMin = clamp(val, MIN_RANGE, targetDuration);
            } else if (dMax <= dTarget && val >= targetDuration) {
                fuzzyMax = clamp(val, targetDuration, MAX_RANGE);
            } else if (val >= fuzzyMin && val <= fuzzyMax) {
                targetDuration = val;
            }
        }
        isDirty = true;
        updateTimelinePositions();
        syncStateToWidgets();
        updateStatus();
    });

    function updateStatus(extraMessage = null) {
        if (extraMessage) {
            statusPanel.innerHTML = extraMessage;
            return;
        }
        if (isDirty) {
            statusPanel.innerHTML = `<div class="xh-status-dirty">⚠️ 参数已发生变化，请点击「开始计算」重新生成缓存。</div>`;
            return;
        }
        statusPanel.innerHTML = `<div>${statusText}</div>`;
    }

    async function updateVideoPreviewAndInfo(filename) {
        if (!filename || filename === "none") {
            videoEl.hidden = true;
            statusText = "未选择视频。";
            isDirty = false;
            updateStatus();
            return;
        }

        const viewUrl = api.apiURL(`/view?filename=${encodeURIComponent(filename)}&type=input`);
        videoEl.src = viewUrl;
        videoEl.hidden = false;
        videoEl.onloadedmetadata = () => {
            resizeNodeToFit(node);
            markDirty(node);
        };

        try {
            const resp = await fetch(api.apiURL(`/xiheha_toolkit/video_info?filename=${encodeURIComponent(filename)}`));
            if (resp.ok) {
                const info = await resp.json();
                statusText = `已加载: <b>${info.filename}</b> | 时长: ${info.duration}s | FPS: ${info.fps} | 分辨率: ${info.width}×${info.height} | 总帧数: ${info.frame_count}`;
            } else {
                statusText = `已加载: ${filename}`;
            }
        } catch {
            statusText = `已加载: ${filename}`;
        }
        isDirty = false;
        updateStatus();
    }

    // Video Widget Change Listener
    const videoWidget = widgetByName(node, "video");
    if (videoWidget) {
        const origCb = videoWidget.callback;
        videoWidget.callback = function (val) {
            origCb?.apply(this, arguments);
            isDirty = false;
            updateVideoPreviewAndInfo(val);
        };
        if (videoWidget.value && videoWidget.value !== "none") {
            updateVideoPreviewAndInfo(videoWidget.value);
        }
    }

    // Watch other parameter widgets to flag isDirty
    const paramWidgets = ["force_rate", "custom_width", "custom_height", "format", "algorithm", "sensitivity", "cut_threshold", "peak_prominence"];
    for (const name of paramWidgets) {
        const w = widgetByName(node, name);
        if (!w) continue;
        const oCb = w.callback;
        w.callback = function () {
            oCb?.apply(this, arguments);
            isDirty = true;
            updateStatus();
        };
    }

    // Upload button click
    uploadBtn.addEventListener("click", () => {
        fileInput.value = "";
        fileInput.click();
    });

    fileInput.addEventListener("change", async () => {
        if (!fileInput.files.length) return;
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append("image", file);

        uploadBtn.disabled = true;
        uploadBtn.textContent = "上传中...";

        try {
            const resp = await api.fetchApi("/upload/image", { method: "POST", body: formData });
            if (resp.ok) {
                const resData = await resp.json();
                const uploadedName = resData.name;
                if (videoWidget) {
                    if (!videoWidget.options.values.includes(uploadedName)) {
                        videoWidget.options.values.push(uploadedName);
                    }
                    videoWidget.value = uploadedName;
                    videoWidget.callback?.(uploadedName);
                }
            } else {
                alert("视频上传失败，请重试。");
            }
        } catch (err) {
            alert(`上传失败: ${err.message}`);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = "上传视频";
        }
    });

    // Calculate button click
    let statusTimer = null;

    calcBtn.addEventListener("click", async () => {
        const curVideo = videoWidget?.value;
        if (!curVideo || curVideo === "none") {
            alert("请先选择或上传需要分割的视频！");
            return;
        }

        calcBtn.disabled = true;
        calcBtn.textContent = "计算中...";
        updateStatus("正在启动视频分析与切片引擎...");

        const payload = {
            node_id: node.id,
            filename: curVideo,
            force_rate: widgetByName(node, "force_rate")?.value ?? 0,
            custom_width: widgetByName(node, "custom_width")?.value ?? 0,
            custom_height: widgetByName(node, "custom_height")?.value ?? 540,
            format: widgetByName(node, "format")?.value ?? "AnimatedDiff",
            split_mode: splitMode,
            fuzzy_min: fuzzyMin,
            target_duration: targetDuration,
            fuzzy_max: fuzzyMax,
            algorithm: widgetByName(node, "algorithm")?.value ?? "智能混合检测（推荐）",
            sensitivity: widgetByName(node, "sensitivity")?.value ?? 0.60,
            cut_threshold: widgetByName(node, "cut_threshold")?.value ?? 0.55,
            peak_prominence: widgetByName(node, "peak_prominence")?.value ?? 0.12,
        };

        // Poll status periodically
        if (statusTimer) clearInterval(statusTimer);
        statusTimer = setInterval(async () => {
            try {
                const sResp = await fetch(api.apiURL(`/xiheha_toolkit/split_status?node_id=${node.id}`));
                if (sResp.ok) {
                    const task = await sResp.json();
                    if (task.status === "running") {
                        updateStatus(task.message);
                    }
                }
            } catch {}
        }, 600);

        try {
            const resp = await api.fetchApi("/xiheha_toolkit/split_video", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (statusTimer) {
                clearInterval(statusTimer);
                statusTimer = null;
            }

            if (resp.ok) {
                const res = await resp.json();
                const count = res.stream?.segments?.length || 0;
                const avg = count > 0 ? (res.stream.segments.reduce((acc, s) => acc + s.duration, 0) / count).toFixed(2) : 0;
                statusText = `✅ 分割完成！生成了 <b>${count}</b> 个视频片段缓存，平均时长 <b>${avg}s</b>。`;
                isDirty = false;
                updateStatus();
            } else {
                const errData = await resp.json().catch(() => ({}));
                statusText = `❌ 计算失败: ${errData.error || "未知错误"}`;
                updateStatus();
            }
        } catch (err) {
            if (statusTimer) {
                clearInterval(statusTimer);
                statusTimer = null;
            }
            statusText = `❌ 请求错误: ${err.message}`;
            updateStatus();
        } finally {
            calcBtn.disabled = false;
            calcBtn.textContent = "开始计算";
            markDirty(node);
        }
    });

    // Mount DOM Widget
    const domWidget = node.addDOMWidget("smart_splitter_ui", "smart_splitter_ui", root, {
        serialize: false,
        hideOnZoom: false,
        computeSize: (w) => [Math.max(MIN_WIDTH, w), Math.max(340, root.offsetHeight || 340)],
    });
    domWidget.element = root;

    // Load persisted state if exists
    if (stateWidget && stateWidget.value) {
        try {
            const parsed = JSON.parse(stateWidget.value);
            if (parsed.split_mode) splitMode = parsed.split_mode;
            if (parsed.fuzzy_min != null) fuzzyMin = Number(parsed.fuzzy_min);
            if (parsed.target_duration != null) targetDuration = Number(parsed.target_duration);
            if (parsed.fuzzy_max != null) fuzzyMax = Number(parsed.fuzzy_max);
        } catch {}
    }

    setMode(splitMode);
    updateTimelinePositions();
    updateWidgetVisibility();
    updateStatus();

    const controller = {
        node,
        root,
        setMode,
        updateStatus,
        dispose() {
            if (statusTimer) clearInterval(statusTimer);
            fileInput?.remove();
        },
    };

    node.__xhSplitter = controller;
    return controller;
}

export function patch(nodeType) {
    setupWidgetTooltips();
    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        origCreated?.apply(this, arguments);
        applyPortLabels(this);
        splitterController(this);
        enforceNodeMinimumSize(this, MIN_WIDTH, MIN_HEIGHT);
        resizeNodeToFit(this);
    };

    const origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function (data) {
        origConfigure?.apply(this, arguments);
        enforceNodeMinimumSize(this, MIN_WIDTH, MIN_HEIGHT);
        resizeNodeToFit(this);
        const stateWidget = widgetByName(this, "splitter_state");
        if (stateWidget?.value && this.__xhSplitter) {
            try {
                const s = JSON.parse(stateWidget.value);
                if (s.fuzzy_min != null && s.target_duration != null && s.fuzzy_max != null) {
                    this.__xhSplitter.setMode(s.split_mode || "fuzzy");
                }
            } catch {}
        }
        applyTooltipMutualExclusion(this);
    };

    const origRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
        hideTooltip();
        this.__xhSplitter?.dispose?.();
        origRemoved?.apply(this, arguments);
    };
}
