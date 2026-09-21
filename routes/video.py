"""Smart video metadata, progress, and split routes."""

from __future__ import annotations

import re
from typing import Any

from aiohttp import web

from ..core.video_meta import get_video_metadata
from ..core.video_pipeline import (
    VideoSplitOptions,
    public_video_metadata,
    public_video_stream,
    resolve_input_video,
    run_video_split,
)


SPLIT_TASKS: dict[str, dict[str, Any]] = {}


def _node_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("node_id 格式无效")
    node_id = str(value)
    if not node_id or len(node_id) > 128 or not re.fullmatch(r"[A-Za-z0-9_.-]+", node_id) or ".." in node_id:
        raise ValueError("node_id 格式无效")
    return node_id


async def video_info(request):
    filename = request.rel_url.query.get("filename", "")
    try:
        _, filepath = resolve_input_video(filename)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except FileNotFoundError:
        return web.json_response({"error": "视频文件不存在"}, status=404)
    try:
        return web.json_response(public_video_metadata(get_video_metadata(filepath)))
    except Exception:
        return web.json_response({"error": "无法读取视频信息"}, status=500)


async def split_status(request):
    value = request.rel_url.query.get("node_id", "")
    if not value:
        return web.json_response({"error": "缺少 node_id 参数"}, status=400)
    try:
        node_id = _node_id(value)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(SPLIT_TASKS.get(node_id, {"status": "idle"}))


async def split_video(request):
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return web.json_response({"error": "请求必须是 JSON"}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({"error": "请求必须是 JSON 对象"}, status=400)

    try:
        node_id = _node_id(payload.get("node_id", "default"))
        _, filepath = resolve_input_video(payload.get("filename", ""))
        options = VideoSplitOptions.from_mapping(payload)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except FileNotFoundError:
        return web.json_response({"error": "视频文件不存在"}, status=404)

    SPLIT_TASKS[node_id] = {
        "status": "running",
        "phase": "starting",
        "current": 0,
        "total": 0,
        "message": "正在准备计算...",
    }

    def progress(phase: str, current: int, total: int) -> None:
        SPLIT_TASKS[node_id] = {
            "status": "running",
            "phase": phase,
            "current": current,
            "total": total,
            "message": f"正在分析镜头: {current}/{total} 帧" if phase == "analyzing" else f"正在生成片段: {current}/{total}",
        }

    try:
        stream, _ = run_video_split(
            filepath,
            node_id,
            options,
            reuse_manifest=False,
            progress_callback=progress,
        )
    except Exception:
        SPLIT_TASKS[node_id] = {
            "status": "error",
            "phase": "error",
            "current": 0,
            "total": 0,
            "message": "视频分割失败",
        }
        return web.json_response({"error": "视频分割失败，请检查视频格式和运行环境"}, status=500)

    segments = stream.get("segments", [])
    total_segments = len(segments)
    average_duration = (
        sum(float(segment.get("duration", 0.0)) for segment in segments) / total_segments
        if total_segments
        else 0.0
    )
    message = f"分割完成！共 {total_segments} 个片段，平均时长 {average_duration:.2f} 秒"
    SPLIT_TASKS[node_id] = {
        "status": "done",
        "phase": "finished",
        "current": total_segments,
        "total": total_segments,
        "message": message,
    }
    return web.json_response({"success": True, "message": message, "stream": public_video_stream(stream)})


def register_video_routes(routes) -> None:
    if hasattr(routes, "get"):
        routes.get("/xiheha_toolkit/video_info")(video_info)
        routes.get("/xiheha_toolkit/split_status")(split_status)
    routes.post("/xiheha_toolkit/split_video")(split_video)
