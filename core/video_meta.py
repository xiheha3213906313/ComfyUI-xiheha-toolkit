"""Video metadata, dimensions, format resolution and audio extraction utilities."""

from __future__ import annotations

import os
import shutil
from fractions import Fraction
from typing import Any

import numpy as np
import torch
import folder_paths

DIMMAX = 8192
BIGMAX = 2**53 - 1
VIDEO_EXTENSIONS = {"webm", "mp4", "mkv", "gif", "mov", "avi", "flv"}

# Supported video model formats aligned with VideoHelperSuite / XB_VideoLoader
LOAD_FORMATS = {
    "None": {},
    "AnimatedDiff": {"target_rate": 8, "dim": (8, 0, 512, 512)},
    "Mochi": {"target_rate": 24, "dim": (16, 0, 848, 480), "frames": (6, 1)},
    "LTXV": {"target_rate": 24, "dim": (32, 0, 768, 512), "frames": (8, 1)},
    "Hunyuan": {"target_rate": 24, "dim": (16, 0, 848, 480), "frames": (4, 1)},
    "Cosmos": {"target_rate": 24, "dim": (16, 0, 1280, 704), "frames": (8, 1)},
    "Wan": {"target_rate": 16, "dim": (8, 0, 832, 480), "frames": (4, 1)},
}


def find_ffmpeg() -> str | None:
    """Find a usable ffmpeg executable."""
    if "VHS_FORCE_FFMPEG_PATH" in os.environ:
        return os.environ["VHS_FORCE_FFMPEG_PATH"]
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg
    for local_name in ("ffmpeg", "ffmpeg.exe"):
        if os.path.isfile(local_name):
            return os.path.abspath(local_name)
    return None


def get_input_video_files() -> list[str]:
    """Scan the ComfyUI input directory for supported video files."""
    input_dir = folder_paths.get_input_directory()
    if not os.path.isdir(input_dir):
        return []
    files: list[str] = []
    for f in os.listdir(input_dir):
        if os.path.isfile(os.path.join(input_dir, f)):
            parts = f.rsplit(".", 1)
            if len(parts) > 1 and parts[1].lower() in VIDEO_EXTENSIONS:
                files.append(f)
    return sorted(files)


def target_size(
    width: int,
    height: int,
    custom_width: int,
    custom_height: int,
    downscale_ratio: int = 8,
) -> tuple[int, int]:
    """Calculate target video width and height based on user overrides and aspect ratio."""
    if downscale_ratio is None or downscale_ratio <= 0:
        downscale_ratio = 8

    out_w = float(width)
    out_h = float(height)

    if custom_width == 0 and custom_height == 0:
        pass
    elif custom_height == 0:
        out_h = height * (custom_width / width)
        out_w = float(custom_width)
    elif custom_width == 0:
        out_w = width * (custom_height / height)
        out_h = float(custom_height)
    else:
        out_w = float(custom_width)
        out_h = float(custom_height)

    final_w = int(out_w / downscale_ratio + 0.5) * downscale_ratio
    final_h = int(out_h / downscale_ratio + 0.5) * downscale_ratio
    return max(final_w, downscale_ratio), max(final_h, downscale_ratio)


def get_video_metadata(video_path: str) -> dict[str, Any]:
    """Extract video dimensions, fps, duration, frame count and audio stream info."""
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if (width <= 0 or height <= 0) and cap.grab():
        _, frame = cap.retrieve()
        if frame is not None:
            height, width = frame.shape[:2]

    cap.release()

    if fps <= 0:
        fps = 30.0

    precise_rate = Fraction(fps).limit_denominator(1_000_000)

    # Check for audio stream presence via PyAV if available
    has_audio = False
    try:
        import av
        with av.open(video_path) as container:
            has_audio = any(s.type == "audio" for s in container.streams)
            video_stream = next((s for s in container.streams if s.type == "video"), None)
            if video_stream is not None and video_stream.average_rate:
                stream_rate = Fraction(
                    int(video_stream.average_rate.numerator),
                    int(video_stream.average_rate.denominator),
                )
                if stream_rate > 0:
                    precise_rate = stream_rate
    except Exception:
        has_audio = False

    precise_fps = float(precise_rate)
    duration = total_frames / precise_fps if total_frames > 0 else 0.0

    return {
        "path": video_path,
        "filename": os.path.basename(video_path),
        "fps": round(precise_fps, 3),
        "_fps_numerator": precise_rate.numerator,
        "_fps_denominator": precise_rate.denominator,
        "width": width,
        "height": height,
        "duration": round(duration, 3),
        "frame_count": total_frames,
        "has_audio": has_audio,
    }


def get_lazy_audio(video_path: str, start_time: float = 0.0, duration: float = 0.0) -> Any:
    """Return ComfyUI compatible AUDIO dict {'waveform': Tensor, 'sample_rate': int}."""
    class _DummyAudio:
        def __getitem__(self, k):
            if k == "waveform":
                return torch.zeros((1, 1, 1), dtype=torch.float32)
            if k == "sample_rate":
                return 44100
            return None
        def __iter__(self):
            return iter({"waveform": torch.zeros((1, 1, 1)), "sample_rate": 44100})
        def __len__(self):
            return 2

    if not os.path.isfile(video_path):
        return _DummyAudio()

    try:
        import av
    except ImportError:
        return _DummyAudio()

    class _LazyAudioMap:
        def __init__(self, file: str, st: float, dur: float):
            self._data = None
            self.file = file
            self.st = st
            self.dur = dur

        def _load(self):
            if self._data is not None:
                return
            try:
                c = av.open(self.file)
                a = next((x for x in c.streams if x.type == "audio"), None)
                if not a:
                    c.close()
                    self._data = {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}
                    return

                sr = a.codec_context.sample_rate or 44100
                frames = []
                sp = int(self.st * sr) if self.st > 0 else 0
                ep = int((self.st + self.dur) * sr) if self.dur > 0 else None

                for f in c.decode(a):
                    if f.pts is not None:
                        if sp > 0 and f.pts < sp:
                            continue
                        if ep is not None and f.pts >= ep:
                            break
                    frames.append(f.to_ndarray())
                c.close()

                if not frames:
                    self._data = {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": sr}
                    return

                wav = np.concatenate(frames, axis=-1)
                if wav.ndim == 1:
                    wav = wav[np.newaxis, :]
                elif wav.shape[0] > 1:
                    wav = wav.mean(axis=0, keepdims=True)
                wf = torch.from_numpy(wav.astype(np.float32))
                if wf.dim() == 2:
                    wf = wf.unsqueeze(0)
                self._data = {"waveform": wf, "sample_rate": sr}
            except Exception:
                self._data = {"waveform": torch.zeros((1, 1, 1), dtype=torch.float32), "sample_rate": 44100}

        def __getitem__(self, k):
            self._load()
            return self._data[k]

        def __iter__(self):
            self._load()
            return iter(self._data)

        def __len__(self):
            self._load()
            return len(self._data)

    return _LazyAudioMap(video_path, start_time, duration)
