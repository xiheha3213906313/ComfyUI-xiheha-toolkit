"""Frame-accurate video cutting, ffmpeg execution, node cache isolation, and manifest generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Callable

import folder_paths

from .video_meta import find_ffmpeg, target_size


_MICROSECONDS_PER_SECOND = 1_000_000


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _format_microseconds(value: int) -> str:
    seconds, microseconds = divmod(value, _MICROSECONDS_PER_SECOND)
    return f"{seconds}.{microseconds:06d}"


def frame_window_timestamps(
    start_frame: int,
    frame_count: int,
    fps_numerator: int,
    fps_denominator: int,
) -> tuple[str, str]:
    """Return a safe input seek and non-truncating duration for an integer frame window."""
    if start_frame < 0 or frame_count <= 0:
        raise ValueError("Frame window must have a non-negative start and positive length")
    if fps_numerator <= 0 or fps_denominator <= 0:
        raise ValueError("Frame rate must be positive")

    start_scaled = start_frame * fps_denominator * _MICROSECONDS_PER_SECOND
    if start_frame == 0:
        seek_microseconds = 0
    else:
        # The largest whole microsecond strictly before the target frame timestamp.
        # This avoids rounding a repeating timestamp upward onto the following frame.
        seek_microseconds = max(0, _ceil_div(start_scaled, fps_numerator) - 1)

    duration_scaled = frame_count * fps_denominator * _MICROSECONDS_PER_SECOND
    duration_microseconds = _ceil_div(duration_scaled, fps_numerator)
    return _format_microseconds(seek_microseconds), _format_microseconds(duration_microseconds)


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
    start_frame: int,
    frame_count: int,
    fps_numerator: int,
    fps_denominator: int,
    target_w: int,
    target_h: int,
    has_audio: bool,
) -> None:
    """Slice a single segment accurately using ffmpeg with video re-encoding and audio preservation."""
    filters = [
        f"scale={target_w}:{target_h}",
        f"trim=end_frame={frame_count}",
        "setpts=PTS-STARTPTS",
    ]
    seek_time, duration = frame_window_timestamps(
        start_frame,
        frame_count,
        fps_numerator,
        fps_denominator,
    )
    frame_rate = f"{fps_numerator}/{fps_denominator}"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-ss", seek_time,
        "-accurate_seek",
        "-i", source_path,
        "-vf", ",".join(filters),
        "-r", frame_rate,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
    ]

    if has_audio:
        cmd.extend([
            "-af", f"atrim=duration={duration},asetpts=PTS-STARTPTS",
            "-c:a", "aac", "-b:a", "192k",
        ])
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
        end_frame = start_frame + frame_count
        raise RuntimeError(f"FFmpeg error cutting frame window [{start_frame}, {end_frame}):\n{proc.stderr}")


def cut_and_cache_segments(
    node_id: str | int,
    source_meta: dict[str, Any],
    segments_plan: list[dict[str, Any]],
    output_w: int,
    output_h: int,
    effective_fps: float,
    fps_numerator: int,
    fps_denominator: int,
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
            start_frame=seg["start_frame"],
            frame_count=seg["frame_count"],
            fps_numerator=fps_numerator,
            fps_denominator=fps_denominator,
            target_w=output_w,
            target_h=output_h,
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
