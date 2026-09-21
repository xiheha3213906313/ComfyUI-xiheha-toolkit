"""Shared validation and execution pipeline for smart video splitting."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import folder_paths

from .scene_detector import split_video_exact, split_video_fuzzy
from .scene_metrics import DETECTION_MODES, REMOVED_DETECTION_MODES
from .video_cutter import cut_and_cache_segments, get_node_cache_dir
from .video_meta import DIMMAX, LOAD_FORMATS, get_video_metadata, target_size


VIDEO_ALGORITHMS = DETECTION_MODES


def _number(
    value: object,
    name: str,
    *,
    minimum: float,
    maximum: float,
    integer: bool = False,
) -> float | int:
    if isinstance(value, bool):
        raise ValueError(f"{name} 必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValueError(f"{name} 超出允许范围")
    if integer:
        if not number.is_integer():
            raise ValueError(f"{name} 必须是整数")
        return int(number)
    return number


@dataclass(frozen=True)
class VideoSplitOptions:
    force_rate: float = 0.0
    custom_width: int = 0
    custom_height: int = 540
    format_name: str = "AnimatedDiff"
    split_mode: str = "fuzzy"
    fuzzy_min: float = 4.0
    target_duration: float = 5.0
    fuzzy_max: float = 6.0
    algorithm: str = VIDEO_ALGORITHMS[0]
    sensitivity: float = 0.60
    cut_threshold: float = 0.55
    peak_prominence: float = 0.12

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "VideoSplitOptions":
        if not isinstance(values, Mapping):
            raise ValueError("视频参数必须是对象")
        format_name = values.get("format", values.get("format_name", "AnimatedDiff"))
        if not isinstance(format_name, str) or format_name not in LOAD_FORMATS:
            raise ValueError("format 不受支持")

        split_mode = values.get("split_mode", "fuzzy")
        if not isinstance(split_mode, str) or split_mode not in {"fuzzy", "exact"}:
            raise ValueError("split_mode 必须是 fuzzy 或 exact")

        algorithm = values.get("algorithm", VIDEO_ALGORITHMS[0])
        if not isinstance(algorithm, str) or algorithm not in VIDEO_ALGORITHMS:
            if isinstance(algorithm, str) and algorithm in REMOVED_DETECTION_MODES:
                raise ValueError("旧检测算法已移除，请重新选择检测模式")
            raise ValueError("algorithm 不受支持")

        fuzzy_min = float(_number(values.get("fuzzy_min", 4.0), "fuzzy_min", minimum=3.0, maximum=15.0))
        target_duration = float(
            _number(values.get("target_duration", 5.0), "target_duration", minimum=3.0, maximum=15.0)
        )
        fuzzy_max = float(_number(values.get("fuzzy_max", 6.0), "fuzzy_max", minimum=3.0, maximum=15.0))

        return cls(
            force_rate=float(_number(values.get("force_rate", 0.0), "force_rate", minimum=0.0, maximum=120.0)),
            custom_width=int(
                _number(values.get("custom_width", 0), "custom_width", minimum=0, maximum=DIMMAX, integer=True)
            ),
            custom_height=int(
                _number(values.get("custom_height", 540), "custom_height", minimum=0, maximum=DIMMAX, integer=True)
            ),
            format_name=format_name,
            split_mode=str(split_mode),
            fuzzy_min=min(fuzzy_min, target_duration),
            target_duration=target_duration,
            fuzzy_max=max(fuzzy_max, target_duration),
            algorithm=algorithm,
            sensitivity=float(
                _number(values.get("sensitivity", 0.60), "sensitivity", minimum=0.0, maximum=1.0)
            ),
            cut_threshold=float(
                _number(values.get("cut_threshold", 0.55), "cut_threshold", minimum=0.0, maximum=1.0)
            ),
            peak_prominence=float(
                _number(values.get("peak_prominence", 0.12), "peak_prominence", minimum=0.0, maximum=1.0)
            ),
        )

    def settings(self) -> dict[str, Any]:
        return {
            "split_mode": self.split_mode,
            "min_duration": self.fuzzy_min,
            "target_duration": self.target_duration,
            "max_duration": self.fuzzy_max,
            "algorithm": self.algorithm,
            "sensitivity": self.sensitivity,
            "cut_threshold": self.cut_threshold,
            "peak_prominence": self.peak_prominence,
            "strong_cut_threshold": 0.75,
        }


def resolve_input_video(filename: object) -> tuple[str, str]:
    if not isinstance(filename, str):
        raise ValueError("filename 必须是字符串")
    cleaned = filename.strip().strip('"').replace("\\", "/")
    if not cleaned or cleaned == "none":
        raise ValueError("请提供 filename")
    if Path(cleaned).is_absolute() or ".." in cleaned.split("/"):
        raise ValueError("filename 必须位于 ComfyUI input 目录")

    input_root = Path(folder_paths.get_input_directory()).resolve()
    try:
        resolved = Path(folder_paths.get_annotated_filepath(cleaned)).resolve()
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("filename 无效") from exc
    if resolved != input_root and input_root not in resolved.parents:
        raise ValueError("filename 必须位于 ComfyUI input 目录")
    if not resolved.is_file():
        raise FileNotFoundError("视频文件不存在")
    return cleaned, os.fspath(resolved)


def _load_reusable_manifest(
    video_path: str,
    node_id: str,
    *,
    output_width: int,
    output_height: int,
    effective_fps: float,
    format_name: str,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    manifest_path = os.path.join(get_node_cache_dir(node_id), "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        source = cached.get("source", {})
        output = cached.get("output", {})
        if (
            source.get("path") == video_path
            and output.get("width") == output_width
            and output.get("height") == output_height
            and output.get("fps") == effective_fps
            and output.get("model_format") == format_name
            and cached.get("settings") == settings
            and all(os.path.isfile(segment.get("path", "")) for segment in cached.get("segments", []))
        ):
            return cached
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def run_video_split(
    video_path: str,
    node_id: str | int,
    options: VideoSplitOptions,
    *,
    reuse_manifest: bool,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    meta = get_video_metadata(video_path)
    effective_fps = options.force_rate if options.force_rate > 0 else float(meta["fps"])
    format_config = LOAD_FORMATS.get(options.format_name, {})
    downscale_ratio = format_config.get("dim", (8,))[0] if "dim" in format_config else 8
    output_width, output_height = target_size(
        meta["width"],
        meta["height"],
        options.custom_width,
        options.custom_height,
        downscale_ratio,
    )
    settings = options.settings()
    cache_key = str(node_id)

    stream = None
    if reuse_manifest:
        stream = _load_reusable_manifest(
            video_path,
            cache_key,
            output_width=output_width,
            output_height=output_height,
            effective_fps=effective_fps,
            format_name=options.format_name,
            settings=settings,
        )

    if stream is None:
        if options.split_mode == "exact":
            segments_plan = split_video_exact(
                total_frames=meta["frame_count"],
                effective_fps=effective_fps,
                target_duration=options.target_duration,
            )
        else:
            segments_plan = split_video_fuzzy(
                video_path=video_path,
                total_frames=meta["frame_count"],
                effective_fps=effective_fps,
                min_duration=options.fuzzy_min,
                target_duration=options.target_duration,
                max_duration=options.fuzzy_max,
                algorithm=options.algorithm,
                sensitivity=options.sensitivity,
                cut_threshold=options.cut_threshold,
                peak_prominence=options.peak_prominence,
                progress_callback=progress_callback,
            )
        stream = cut_and_cache_segments(
            node_id=cache_key,
            source_meta=meta,
            segments_plan=segments_plan,
            output_w=output_width,
            output_h=output_height,
            effective_fps=effective_fps,
            model_format=options.format_name,
            split_mode=options.split_mode,
            settings=settings,
            progress_callback=progress_callback,
        )
    return stream, meta


def public_video_metadata(meta: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("filename", "fps", "width", "height", "duration", "frame_count", "has_audio")
    return {key: meta[key] for key in fields if key in meta}


def public_video_stream(stream: Mapping[str, Any]) -> dict[str, Any]:
    source_fields = ("filename", "fps", "effective_fps", "width", "height", "duration", "frame_count")
    output_fields = ("width", "height", "fps", "model_format")
    segment_fields = (
        "index",
        "start_time",
        "end_time",
        "duration",
        "start_frame",
        "end_frame",
        "frame_count",
        "cut_score",
        "cut_type",
        "constraint_warning",
    )
    source_data = stream.get("source", {})
    output_data = stream.get("output", {})
    source = (
        {key: source_data[key] for key in source_fields if key in source_data}
        if isinstance(source_data, Mapping)
        else {}
    )
    output = (
        {key: output_data[key] for key in output_fields if key in output_data}
        if isinstance(output_data, Mapping)
        else {}
    )
    segments = [
        {key: segment[key] for key in segment_fields if key in segment}
        for segment in stream.get("segments", [])
        if isinstance(segment, Mapping)
    ]
    return {
        "version": stream.get("version", 1),
        "split_mode": stream.get("split_mode", "fuzzy"),
        "source": source,
        "output": output,
        "segments": segments,
    }
