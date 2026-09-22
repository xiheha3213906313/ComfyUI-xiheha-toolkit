"""Frame-boundary regression tests for smart-video FFmpeg cutting."""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from core.video_cutter import cut_single_segment, frame_window_timestamps
from core.video_meta import find_ffmpeg, get_video_metadata


def _decode_frames(path: str) -> list[np.ndarray]:
    capture = cv2.VideoCapture(path)
    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    return frames


def _nearest_source_indices(outputs: list[np.ndarray], sources: list[np.ndarray]) -> list[int]:
    indices: list[int] = []
    source_arrays = [frame.astype(np.int16) for frame in sources]
    for output in outputs:
        output_array = output.astype(np.int16)
        indices.append(min(
            range(len(source_arrays)),
            key=lambda index: float(np.mean(np.abs(output_array - source_arrays[index]))),
        ))
    return indices


class FrameTimestampTests(unittest.TestCase):
    def test_repeating_frame_timestamp_is_never_rounded_past_target(self):
        seek, duration = frame_window_timestamps(283, 80, 24, 1)
        self.assertEqual(seek, "11.791666")
        self.assertEqual(duration, "3.333334")

    def test_zero_start_and_invalid_windows(self):
        self.assertEqual(frame_window_timestamps(0, 7, 24, 1), ("0.000000", "0.291667"))
        with self.assertRaises(ValueError):
            frame_window_timestamps(-1, 1, 24, 1)
        with self.assertRaises(ValueError):
            frame_window_timestamps(0, 0, 24, 1)
        with self.assertRaises(ValueError):
            frame_window_timestamps(0, 1, 0, 1)

    @patch("core.video_cutter.subprocess.run")
    def test_ffmpeg_command_uses_integer_frame_window(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        cut_single_segment(
            ffmpeg_exe="ffmpeg",
            source_path="source.mp4",
            output_path="segment.mp4",
            start_frame=283,
            frame_count=80,
            fps_numerator=24,
            fps_denominator=1,
            target_w=1280,
            target_h=720,
            has_audio=True,
        )

        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-ss") + 1], "11.791666")
        self.assertEqual(command[command.index("-r") + 1], "24/1")
        self.assertLess(command.index("-ss"), command.index("-i"))
        self.assertIn("-accurate_seek", command)
        self.assertEqual(
            command[command.index("-vf") + 1],
            "scale=1280:720,trim=end_frame=80,setpts=PTS-STARTPTS",
        )
        self.assertEqual(
            command[command.index("-af") + 1],
            "atrim=duration=3.333334,asetpts=PTS-STARTPTS",
        )
        self.assertNotIn("-t", command)
        self.assertNotIn("-frames:v", command)
        self.assertNotIn("-shortest", command)


class SyntheticFrameBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = find_ffmpeg()
        if not cls.ffmpeg:
            raise unittest.SkipTest("FFmpeg is required for frame-boundary integration tests")

    def test_adjacent_audio_segments_have_no_gap_overlap_or_foreign_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = os.path.join(temporary, "source.mkv")
            first = os.path.join(temporary, "first.mp4")
            exact_five = os.path.join(temporary, "exact_five.mp4")
            middle = os.path.join(temporary, "middle.mp4")
            tail = os.path.join(temporary, "tail.mp4")
            long_audio = os.path.join(temporary, "long_audio.mp4")

            generated = subprocess.run(
                [
                    self.ffmpeg,
                    "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi",
                    "-i", "testsrc2=size=160x90:rate=24:duration=6,negate=enable='gte(n,7)'",
                    "-f", "lavfi",
                    "-i", "sine=frequency=1000:sample_rate=32000:duration=6",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "ffv1", "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", "-shortest", source,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)

            metadata = get_video_metadata(source)
            self.assertEqual((metadata["_fps_numerator"], metadata["_fps_denominator"]), (24, 1))
            self.assertEqual(metadata["frame_count"], 144)

            for output, start, count, has_audio in (
                (first, 0, 7, True),
                (exact_five, 0, 120, True),
                (middle, 7, 9, True),
                (tail, 136, 8, False),
                (long_audio, 7, 80, True),
            ):
                cut_single_segment(
                    ffmpeg_exe=self.ffmpeg,
                    source_path=source,
                    output_path=output,
                    start_frame=start,
                    frame_count=count,
                    fps_numerator=24,
                    fps_denominator=1,
                    target_w=160,
                    target_h=90,
                    has_audio=has_audio,
                )

            source_frames = _decode_frames(source)
            first_frames = _decode_frames(first)
            exact_five_frames = _decode_frames(exact_five)
            middle_frames = _decode_frames(middle)
            tail_frames = _decode_frames(tail)
            long_audio_frames = _decode_frames(long_audio)

            self.assertEqual(len(first_frames), 7)
            self.assertEqual(len(exact_five_frames), 120)
            self.assertEqual(len(middle_frames), 9)
            self.assertEqual(len(tail_frames), 8)
            self.assertEqual(len(long_audio_frames), 80)
            self.assertEqual(_nearest_source_indices(first_frames, source_frames), list(range(0, 7)))
            self.assertEqual(
                _nearest_source_indices([exact_five_frames[0], exact_five_frames[-1]], source_frames),
                [0, 119],
            )
            self.assertEqual(_nearest_source_indices(middle_frames, source_frames), list(range(7, 16)))
            self.assertEqual(_nearest_source_indices(tail_frames, source_frames), list(range(136, 144)))
            self.assertEqual(
                _nearest_source_indices([long_audio_frames[0], long_audio_frames[-1]], source_frames),
                [7, 86],
            )

            try:
                import av
            except ImportError:
                return
            with av.open(middle) as container:
                self.assertTrue(any(stream.type == "audio" for stream in container.streams))
            with av.open(tail) as container:
                self.assertFalse(any(stream.type == "audio" for stream in container.streams))
            with av.open(exact_five) as container:
                video_stream = next(stream for stream in container.streams if stream.type == "video")
                audio_stream = next(stream for stream in container.streams if stream.type == "audio")
                self.assertAlmostEqual(float(video_stream.duration * video_stream.time_base), 5.0, places=6)
                self.assertAlmostEqual(float(audio_stream.duration * audio_stream.time_base), 5.0, places=6)
                self.assertAlmostEqual(float(container.duration / av.time_base), 5.0, places=6)
            with av.open(long_audio) as container:
                video_stream = next(stream for stream in container.streams if stream.type == "video")
                audio_stream = next(stream for stream in container.streams if stream.type == "audio")
                video_duration = float(video_stream.duration * video_stream.time_base)
                audio_duration = float(audio_stream.duration * audio_stream.time_base)
                sample_rate = int(audio_stream.codec_context.sample_rate)
                container_duration = float(container.duration / av.time_base)
            with av.open(long_audio) as container:
                audio_stream = next(stream for stream in container.streams if stream.type == "audio")
                decoded_samples = sum(frame.samples for frame in container.decode(audio_stream))

            required_samples = math.ceil((80 / 24) * sample_rate)
            self.assertEqual(video_duration, 80 / 24)
            self.assertGreaterEqual(audio_duration, video_duration)
            self.assertLessEqual(container_duration - video_duration, 0.001)
            self.assertGreaterEqual(decoded_samples, required_samples)


if __name__ == "__main__":
    unittest.main()
