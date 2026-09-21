"""Regression tests for the shared smart-video execution pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import video_pipeline
from core.video_pipeline import VideoSplitOptions, public_video_stream, run_video_split
from nodes import smart_video_splitter as splitter_node


class VideoPipelineTests(unittest.TestCase):
    def test_split_modes_keep_legacy_target_semantics_and_normalize_scene_range(self):
        target = VideoSplitOptions.from_mapping({
            "split_mode": "fuzzy",
            "fuzzy_min": 12,
            "target_duration": 5,
            "fuzzy_max": 4,
        })
        self.assertEqual((target.fuzzy_min, target.target_duration, target.fuzzy_max), (5.0, 5.0, 5.0))

        scene = VideoSplitOptions.from_mapping({
            "split_mode": "scene",
            "fuzzy_min": 12,
            "target_duration": 3,
            "fuzzy_max": 4,
        })
        self.assertEqual(scene.split_mode, "scene")
        self.assertEqual((scene.fuzzy_min, scene.fuzzy_max), (4.0, 12.0))
        self.assertEqual(scene.target_duration, 3.0)

    def test_scene_mode_delegates_to_earliest_selection_policy(self):
        metadata = {
            "path": "video.mp4", "filename": "video.mp4", "fps": 24.0,
            "width": 640, "height": 480, "duration": 3.0,
            "frame_count": 72, "has_audio": False,
        }
        options = VideoSplitOptions(split_mode="scene")
        stream = {"segments": []}
        with patch.object(video_pipeline, "get_video_metadata", return_value=metadata), patch.object(
            video_pipeline, "target_size", return_value=(640, 480)
        ), patch.object(video_pipeline, "split_video_fuzzy", return_value=[]) as split_scene, patch.object(
            video_pipeline, "cut_and_cache_segments", return_value=stream
        ):
            result, _ = run_video_split("video.mp4", "scene-test", options, reuse_manifest=False)
        self.assertIs(result, stream)
        self.assertEqual(split_scene.call_args.kwargs["selection_policy"], "earliest")

    def test_manifest_is_reused_only_through_shared_pipeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "video.mp4"
            segment = root / "segment_0001.mp4"
            video.write_bytes(b"video")
            segment.write_bytes(b"segment")
            options = VideoSplitOptions(split_mode="exact")
            metadata = {
                "path": str(video), "filename": video.name, "fps": 24.0,
                "width": 640, "height": 480, "duration": 3.0,
                "frame_count": 72, "has_audio": False,
            }
            manifest = {
                "version": 1,
                "split_mode": "exact",
                "source": {"path": str(video), "filename": video.name},
                "output": {"width": 640, "height": 480, "fps": 24.0, "model_format": "AnimatedDiff"},
                "settings": options.settings(),
                "cache_dir": str(root),
                "segments": [{"path": str(segment), "duration": 3.0, "frame_count": 72}],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / ".pipeline_revision").write_text(
                video_pipeline.PIPELINE_CACHE_REVISION,
                encoding="utf-8",
            )
            with patch.object(video_pipeline, "get_node_cache_dir", return_value=str(root)), patch.object(
                video_pipeline, "get_video_metadata", return_value=metadata
            ), patch.object(video_pipeline, "target_size", return_value=(640, 480)), patch.object(
                video_pipeline, "split_video_exact"
            ) as split_exact, patch.object(video_pipeline, "cut_and_cache_segments") as cut:
                stream, returned_meta = run_video_split(str(video), "7", options, reuse_manifest=True)
            self.assertEqual(stream, manifest)
            self.assertIs(returned_meta, metadata)
            split_exact.assert_not_called()
            cut.assert_not_called()

    def test_manifest_without_current_pipeline_revision_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "video.mp4"
            segment = root / "segment_0001.mp4"
            video.write_bytes(b"video")
            segment.write_bytes(b"segment")
            options = VideoSplitOptions(split_mode="exact")
            metadata = {
                "path": str(video), "filename": video.name, "fps": 24.0,
                "width": 640, "height": 480, "duration": 3.0,
                "frame_count": 72, "has_audio": False,
            }
            stale_manifest = {
                "version": 1,
                "split_mode": "exact",
                "source": {"path": str(video), "filename": video.name},
                "output": {"width": 640, "height": 480, "fps": 24.0, "model_format": "AnimatedDiff"},
                "settings": options.settings(),
                "cache_dir": str(root),
                "segments": [{"path": str(segment), "duration": 3.0, "frame_count": 72}],
            }
            fresh_manifest = {**stale_manifest, "segments": []}
            (root / "manifest.json").write_text(json.dumps(stale_manifest), encoding="utf-8")
            with patch.object(video_pipeline, "get_node_cache_dir", return_value=str(root)), patch.object(
                video_pipeline, "get_video_metadata", return_value=metadata
            ), patch.object(video_pipeline, "target_size", return_value=(640, 480)), patch.object(
                video_pipeline, "split_video_exact", return_value=[]
            ) as split_exact, patch.object(
                video_pipeline, "cut_and_cache_segments", return_value=fresh_manifest
            ) as cut:
                stream, _ = run_video_split(str(video), "7", options, reuse_manifest=True)
            self.assertIs(stream, fresh_manifest)
            split_exact.assert_called_once()
            cut.assert_called_once()

    def test_node_adapts_shared_pipeline_result_without_reimplementing_it(self):
        stream = {"segments": [{"frame_count": 12}, {"frame_count": 8}]}
        metadata = {"duration": 2.0}
        audio = object()
        with patch.object(splitter_node, "resolve_input_video", return_value=("video.mp4", "safe/video.mp4")), patch.object(
            splitter_node, "run_video_split", return_value=(stream, metadata)
        ) as run, patch.object(splitter_node, "get_lazy_audio", return_value=audio):
            result = splitter_node.SmartVideoSplitter().process("video.mp4", unique_id="9")
        self.assertIs(result[0], stream)
        self.assertIs(result[1], audio)
        self.assertEqual(result[2], 20)
        self.assertTrue(run.call_args.kwargs["reuse_manifest"])

    def test_public_stream_removes_all_internal_paths(self):
        public = public_video_stream({
            "version": 1,
            "split_mode": "fuzzy",
            "cache_dir": "C:/secret/cache",
            "source": {"path": "C:/secret/input.mp4", "filename": "input.mp4"},
            "output": {"width": 640},
            "settings": {},
            "segments": [{"path": "C:/secret/segment.mp4", "filename": "segment.mp4"}],
        })
        self.assertNotIn("cache_dir", public)
        self.assertNotIn("path", public["source"])
        self.assertNotIn("path", public["segments"][0])


if __name__ == "__main__":
    unittest.main()
