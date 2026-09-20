"""Frame-accurate video cutting, ffmpeg execution, node cache isolation, and manifest generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Callable

import folder_paths

from .video_meta import find_ffmpeg, target_size


def get_node_cache_dir(node_id: str | int) -> str:
    """Return isolated temporary cache directory for a specific node instance."""
    safe_node_id = str(node_id).replace("/", "_").replace("\\", "_").replace("..", "")
    temp_dir = folder_paths.get_temp_directory()
    cache_dir = os.path.join(temp_dir, "intelligent_video_splitter", f"node_{safe_node_id}")
    return cache_dir


def clean_node_cache(node_id: str | int) -> str:
    """Safely wipe only the current node instance's cache directory and recreate it."""
    cache_dir = get_node_cache_dir(node_id)
    if os.path.exists(cache_dir):
        # Double check containment to prevent wiping unexpected directories
        temp_dir = folder_paths.get_temp_directory()
        if os.path.commonpath([os.path.abspath(cache_dir), os.path.abspath(temp_dir)]) == os.path.abspath(temp_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def cut_single_segment(
    ffmpeg_exe: str,
    source_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    target_w: int,
    target_h: int,
    fps: float,
    has_audio: bool,
) -> None:
    """Slice a single segment accurately using ffmpeg with video re-encoding and audio preservation."""
    filters = [f"scale={target_w}:{target_h}"]

    cmd = [
        ffmpeg_exe,
        "-y",
        "-ss", f"{start_time:.3f}",
        "-t", f"{duration:.3f}",
        "-i", source_path,
        "-vf", ",".join(filters),
        "-r", f"{fps:.3f}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
    ]

    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.append("-an")

    cmd.append(output_path)

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error cutting segment ({start_time}-{start_time+duration}):\n{proc.stderr}")


def cut_and_cache_segments(
    node_id: str | int,
    source_meta: dict[str, Any],
    segments_plan: list[dict[str, Any]],
    output_w: int,
    output_h: int,
    effective_fps: float,
    model_format: str,
    split_mode: str,
    settings: dict[str, Any],
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Execute the cutting plan, store segments in the node's isolated cache, and produce SMART_VIDEO_STREAM."""
    ffmpeg_exe = find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg executable not found. Please install ffmpeg or imageio-ffmpeg.")

    cache_dir = clean_node_cache(node_id)
    source_path = source_meta["path"]
    has_audio = source_meta.get("has_audio", False)

    cached_segments: list[dict[str, Any]] = []
    total_segs = len(segments_plan)

    for idx, seg in enumerate(segments_plan):
        seg_filename = f"segment_{idx + 1:04d}.mp4"
        seg_filepath = os.path.join(cache_dir, seg_filename)

        if progress_callback:
            progress_callback("generating", idx + 1, total_segs)

        cut_single_segment(
            ffmpeg_exe=ffmpeg_exe,
            source_path=source_path,
            output_path=seg_filepath,
            start_time=seg["start_time"],
            duration=seg["duration"],
            target_w=output_w,
            target_h=output_h,
            fps=effective_fps,
            has_audio=has_audio,
        )

        cached_segments.append({
            "index": idx,
            "path": seg_filepath,
            "filename": seg_filename,
            "start_time": seg["start_time"],
            "end_time": seg["end_time"],
            "duration": seg["duration"],
            "start_frame": seg["start_frame"],
            "end_frame": seg["end_frame"],
            "frame_count": seg["frame_count"],
            "cut_score": seg["cut_score"],
            "cut_type": seg["cut_type"],
            "constraint_warning": seg.get("constraint_warning", False),
        })

    smart_video_stream = {
        "version": 1,
        "split_mode": split_mode,
        "source": {
            "path": source_path,
            "filename": source_meta.get("filename", os.path.basename(source_path)),
            "fps": source_meta.get("fps", effective_fps),
            "effective_fps": effective_fps,
            "width": source_meta.get("width", output_w),
            "height": source_meta.get("height", output_h),
            "duration": source_meta.get("duration", 0.0),
            "frame_count": source_meta.get("frame_count", 0),
        },
        "output": {
            "width": output_w,
            "height": output_h,
            "fps": effective_fps,
            "model_format": model_format,
        },
        "settings": settings,
        "cache_dir": cache_dir,
        "segments": cached_segments,
    }

    manifest_path = os.path.join(cache_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(smart_video_stream, f, indent=2, ensure_ascii=False)

    return smart_video_stream
