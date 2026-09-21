import { createTimeline } from "./timeline.js";

export function createSplitterView(callbacks) {
    const actionBar = document.createElement("div");
    actionBar.className = "xh-action-bar";
    const uploadButton = document.createElement("button");
    uploadButton.className = "xh-action-btn";
    uploadButton.type = "button";
    uploadButton.textContent = "上传视频";
    const calculateButton = document.createElement("button");
    calculateButton.className = "xh-action-btn primary";
    calculateButton.type = "button";
    calculateButton.textContent = "开始计算";
    actionBar.append(uploadButton, calculateButton);

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "video/mp4,video/webm,video/x-matroska,video/quicktime,video/avi,image/gif";
    fileInput.style.display = "none";
    document.body.appendChild(fileInput);
    uploadButton.addEventListener("click", () => { fileInput.value = ""; fileInput.click(); });
    fileInput.addEventListener("change", () => {
        const file = fileInput.files?.[0];
        if (file) callbacks.onUpload(file);
    });
    calculateButton.addEventListener("click", callbacks.onCalculate);

    const timeline = createTimeline({ onChange: callbacks.onTimelineChange });
    const previewContainer = document.createElement("div");
    previewContainer.className = "xh-preview-container";
    const video = document.createElement("video");
    video.className = "xh-preview-video";
    video.controls = true;
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    video.hidden = true;
    previewContainer.appendChild(video);
    const status = document.createElement("div");
    status.className = "xh-status-panel";

    return {
        elements: [actionBar, timeline.element, previewContainer, status],
        uploadButton, calculateButton, video, status, timeline,
        dispose() { timeline.dispose(); video.removeAttribute("src"); video.load?.(); fileInput.remove(); },
    };
}
