import { api } from "../../../../scripts/api.js";

async function jsonResponse(response, fallbackMessage) {
    let payload = {};
    try { payload = await response.json(); } catch { /* status fallback below */ }
    if (!response.ok) throw new Error(payload?.error || `${fallbackMessage} (${response.status})`);
    return payload;
}

export function apiUrl(path) {
    return api.apiURL(path);
}

export async function getVideoInfo(filename) {
    const response = await api.fetchApi(`/xiheha_toolkit/video_info?filename=${encodeURIComponent(filename)}`);
    return jsonResponse(response, "视频信息读取失败");
}

export async function getSplitStatus(nodeId) {
    const response = await api.fetchApi(`/xiheha_toolkit/split_status?node_id=${encodeURIComponent(nodeId)}`);
    return jsonResponse(response, "切分状态读取失败");
}

export async function uploadVideo(file) {
    const body = new FormData();
    body.append("image", file);
    const response = await api.fetchApi("/upload/image", { method: "POST", body });
    return jsonResponse(response, "视频上传失败");
}

export async function splitVideo(payload) {
    const response = await api.fetchApi("/xiheha_toolkit/split_video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return jsonResponse(response, "视频切分失败");
}
