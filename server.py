"""Local HTTP endpoints used by the toolkit frontend."""

from __future__ import annotations

import os
from typing import Any

from aiohttp import web
import folder_paths
from server import PromptServer

from .core.config_parser import (
    commit_source_config_save,
    inspect_sources,
    prepare_source_config_save,
)


_REGISTERED = False
_MAX_SOURCES = 100
_MAX_CONFIGS = 100
_MAX_PROMPT_LENGTH = 100_000


def _validated_save_sources(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("sources 必须是数组")
    if len(sources) > _MAX_SOURCES:
        raise ValueError("一次最多保存 100 个来源")

    validated: list[dict[str, object]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("来源项格式无效")
        source_name = source.get("source_name")
        folder_name = source.get("folder_name", "loras")
        configs = source.get("configs")
        if not isinstance(source_name, str) or not isinstance(folder_name, str):
            raise ValueError("模型名称和目录必须是字符串")
        if not isinstance(configs, list):
            raise ValueError("configs 必须是数组")
        if len(configs) > _MAX_CONFIGS:
            raise ValueError("每个模型最多保存 100 个配置")

        validated_configs: list[dict[str, object]] = []
        for config in configs:
            if not isinstance(config, dict):
                raise ValueError("配置项格式无效")
            index = config.get("index")
            positive = config.get("positive", "")
            negative = config.get("negative", "")
            if not isinstance(index, int) or isinstance(index, bool) or index < 1:
                raise ValueError("配置编号必须是正整数")
            if not isinstance(positive, str) or not isinstance(negative, str):
                raise ValueError("提示词必须是字符串")
            if len(positive) > _MAX_PROMPT_LENGTH or len(negative) > _MAX_PROMPT_LENGTH:
                raise ValueError("单项提示词不能超过 100000 个字符")
            validated_configs.append({"index": index, "positive": positive, "negative": negative})
        validated.append({"source_name": source_name, "folder_name": folder_name, "configs": validated_configs})
    return validated


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    prompt_server = PromptServer.instance

    @prompt_server.routes.post("/xiheha_toolkit/inspect")
    async def inspect(request):
        try:
            payload = await request.json()
        except (TypeError, ValueError):
            return web.json_response({"error": "请求必须是 JSON"}, status=400)

        sources = payload.get("sources", []) if isinstance(payload, dict) else []
        if not isinstance(sources, list):
            return web.json_response({"error": "sources 必须是数组"}, status=400)
        if len(sources) > _MAX_SOURCES:
            return web.json_response({"error": "一次最多扫描 100 个来源"}, status=400)

        safe_sources = [
            {
                "source_name": source.get("source_name", ""),
                "folder_name": source.get("folder_name", "loras"),
            }
            for source in sources
            if isinstance(source, dict)
            and isinstance(source.get("source_name", ""), str)
            and isinstance(source.get("folder_name", "loras"), str)
        ]
        return web.json_response({"sources": inspect_sources(safe_sources)})

    @prompt_server.routes.post("/xiheha_toolkit/save")
    async def save(request):
        try:
            payload = await request.json()
        except (TypeError, ValueError):
            return web.json_response({"error": "请求必须是 JSON"}, status=400)

        try:
            sources = _validated_save_sources(payload)
            plans = [
                prepare_source_config_save(source["source_name"], source["folder_name"], source["configs"])
                for source in sources
            ]
        except ValueError as exc:
            return web.json_response({"error": str(exc) or "配置保存请求无效"}, status=400)

        try:
            inspections = [commit_source_config_save(plan).to_dict() for plan in plans]
        except (OSError, UnicodeError):
            return web.json_response({"error": "配置保存失败，请检查文件权限"}, status=500)
        return web.json_response({"sources": inspections})

    _SPLIT_TASKS: dict[str, dict[str, Any]] = {}

    if hasattr(prompt_server.routes, "get"):
        @prompt_server.routes.get("/xiheha_toolkit/video_info")
        async def video_info(request):
            filename = request.rel_url.query.get("filename", "")
            if not filename:
                return web.json_response({"error": "缺少 filename 参数"}, status=400)
            try:
                cleaned = filename.strip().strip('"')
                filepath = folder_paths.get_annotated_filepath(cleaned)
                if not os.path.isfile(filepath):
                    return web.json_response({"error": "视频文件不存在"}, status=404)
                try:
                    from .core.video_meta import get_video_metadata
                except (ImportError, ValueError):
                    from core.video_meta import get_video_metadata
                meta = get_video_metadata(filepath)
                return web.json_response(meta)
            except Exception as exc:
                return web.json_response({"error": str(exc)}, status=500)

        @prompt_server.routes.get("/xiheha_toolkit/split_status")
        async def split_status(request):
            node_id = request.rel_url.query.get("node_id", "")
            if not node_id:
                return web.json_response({"error": "缺少 node_id 参数"}, status=400)
            task = _SPLIT_TASKS.get(str(node_id), {"status": "idle"})
            return web.json_response(task)

    @prompt_server.routes.post("/xiheha_toolkit/split_video")
    async def split_video(request):
        try:
            payload = await request.json()
        except (TypeError, ValueError):
            return web.json_response({"error": "请求必须是 JSON"}, status=400)

        node_id = str(payload.get("node_id", "default"))
        filename = payload.get("filename", "")
        if not filename:
            return web.json_response({"error": "请提供 filename"}, status=400)

        cleaned = filename.strip().strip('"')
        filepath = folder_paths.get_annotated_filepath(cleaned)
        if not os.path.isfile(filepath):
            return web.json_response({"error": "视频文件不存在"}, status=404)

        try:
            from .core.video_meta import get_video_metadata, target_size, LOAD_FORMATS
            from .core.scene_detector import split_video_fuzzy, split_video_exact
            from .core.video_cutter import cut_and_cache_segments
        except (ImportError, ValueError):
            from core.video_meta import get_video_metadata, target_size, LOAD_FORMATS
            from core.scene_detector import split_video_fuzzy, split_video_exact
            from core.video_cutter import cut_and_cache_segments

        _SPLIT_TASKS[node_id] = {
            "status": "running",
            "phase": "starting",
            "current": 0,
            "total": 0,
            "message": "正在准备计算...",
        }

        try:
            meta = get_video_metadata(filepath)
            force_rate = float(payload.get("force_rate", 0.0))
            effective_fps = force_rate if force_rate > 0 else float(meta["fps"])

            custom_width = int(payload.get("custom_width", 0))
            custom_height = int(payload.get("custom_height", 540))
            format_name = payload.get("format", "AnimatedDiff")

            fmt_config = LOAD_FORMATS.get(format_name, {})
            downscale_ratio = fmt_config.get("dim", (8,))[0] if "dim" in fmt_config else 8
            out_w, out_h = target_size(meta["width"], meta["height"], custom_width, custom_height, downscale_ratio)

            split_mode = payload.get("split_mode", "fuzzy")
            fuzzy_min = float(payload.get("fuzzy_min", 4.0))
            target_duration = float(payload.get("target_duration", 5.0))
            fuzzy_max = float(payload.get("fuzzy_max", 6.0))

            f_min = min(fuzzy_min, target_duration)
            f_target = target_duration
            f_max = max(fuzzy_max, target_duration)

            algorithm = payload.get("algorithm", "智能混合检测（推荐）")
            sensitivity = float(payload.get("sensitivity", 0.60))
            cut_threshold = float(payload.get("cut_threshold", 0.55))
            peak_prominence = float(payload.get("peak_prominence", 0.12))

            settings = {
                "split_mode": split_mode,
                "min_duration": f_min,
                "target_duration": f_target,
                "max_duration": f_max,
                "algorithm": algorithm,
                "sensitivity": sensitivity,
                "cut_threshold": cut_threshold,
                "peak_prominence": peak_prominence,
                "strong_cut_threshold": 0.75,
            }

            def _progress_cb(phase: str, cur: int, tot: int):
                _SPLIT_TASKS[node_id] = {
                    "status": "running",
                    "phase": phase,
                    "current": cur,
                    "total": tot,
                    "message": f"正在分析镜头: {cur}/{tot} 帧" if phase == "analyzing" else f"正在生成片段: {cur}/{tot}",
                }

            total_frames = meta["frame_count"]
            if split_mode == "exact":
                segments_plan = split_video_exact(
                    total_frames=total_frames,
                    effective_fps=effective_fps,
                    target_duration=f_target,
                )
            else:
                segments_plan = split_video_fuzzy(
                    video_path=filepath,
                    total_frames=total_frames,
                    effective_fps=effective_fps,
                    min_duration=f_min,
                    target_duration=f_target,
                    max_duration=f_max,
                    algorithm=algorithm,
                    sensitivity=sensitivity,
                    cut_threshold=cut_threshold,
                    peak_prominence=peak_prominence,
                    progress_callback=_progress_cb,
                )

            stream_data = cut_and_cache_segments(
                node_id=node_id,
                source_meta=meta,
                segments_plan=segments_plan,
                output_w=out_w,
                output_h=out_h,
                effective_fps=effective_fps,
                model_format=format_name,
                split_mode=split_mode,
                settings=settings,
                progress_callback=_progress_cb,
            )

            total_segs = len(stream_data.get("segments", []))
            avg_dur = (
                sum(s["duration"] for s in stream_data.get("segments", [])) / total_segs
                if total_segs > 0
                else 0.0
            )

            _SPLIT_TASKS[node_id] = {
                "status": "done",
                "phase": "finished",
                "current": total_segs,
                "total": total_segs,
                "message": f"分割完成！共 {total_segs} 个片段，平均时长 {avg_dur:.2f} 秒",
                "stream": stream_data,
            }

            return web.json_response({
                "success": True,
                "message": _SPLIT_TASKS[node_id]["message"],
                "stream": stream_data,
            })

        except Exception as exc:
            _SPLIT_TASKS[node_id] = {
                "status": "error",
                "phase": "error",
                "current": 0,
                "total": 0,
                "message": f"计算失败: {str(exc)}",
            }
            return web.json_response({"error": str(exc)}, status=500)

    _REGISTERED = True
