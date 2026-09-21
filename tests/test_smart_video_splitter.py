"""Comprehensive tests for the Smart Video Splitter node and engine."""

import os
import shutil
import subprocess
import tempfile
import unittest
import numpy as np
import torch

from core.video_meta import (
    LOAD_FORMATS,
    get_lazy_audio,
    target_size,
)
from core.scene_detector import (
    compute_cut_score,
    compute_edge_diff,
    compute_frame_diff,
    compute_hsv_diff,
    compute_phash_diff,
    compute_ssim_diff,
    select_best_cut,
    split_video_exact,
)
from core.video_cutter import (
    clean_node_cache,
    get_node_cache_dir,
)
from nodes.smart_video_splitter import SmartVideoSplitter
import folder_paths


class TestSmartVideoSplitterContract(unittest.TestCase):
    """Verify node contract, parameter declarations, input/output types and mappings."""

    def test_node_inputs(self):
        inputs = SmartVideoSplitter.INPUT_TYPES()
        self.assertIn("required", inputs)
        req = inputs["required"]

        # Verify required widgets
        self.assertIn("video", req)
        self.assertIn("force_rate", req)
        self.assertIn("custom_width", req)
        self.assertIn("custom_height", req)
        self.assertIn("format", req)
        self.assertIn("split_mode", req)
        self.assertIn("fuzzy_min", req)
        self.assertIn("target_duration", req)
        self.assertIn("fuzzy_max", req)
        self.assertIn("algorithm", req)
        self.assertIn("sensitivity", req)
        self.assertIn("cut_threshold", req)
        self.assertIn("peak_prominence", req)

        # Removed features must NOT be present
        self.assertNotIn("frame_load_cap", req)
        self.assertNotIn("skip_first_frames", req)
        self.assertNotIn("select_every_nth", req)

        # Defaults
        self.assertEqual(req["force_rate"][1]["default"], 0.0)
        self.assertEqual(req["custom_width"][1]["default"], 0)
        self.assertEqual(req["custom_height"][1]["default"], 540)
        self.assertEqual(req["format"][1]["default"], "AnimatedDiff")
        self.assertEqual(req["fuzzy_min"][1]["default"], 4.0)
        self.assertEqual(req["target_duration"][1]["default"], 5.0)
        self.assertEqual(req["fuzzy_max"][1]["default"], 6.0)

        # Hidden fields
        self.assertIn("hidden", inputs)
        self.assertEqual(inputs["hidden"].get("unique_id"), "UNIQUE_ID")
        self.assertEqual(inputs["hidden"].get("splitter_state"), "STRING")

    def test_tooltips_declared_for_config_options(self):
        inputs = SmartVideoSplitter.INPUT_TYPES()
        req = inputs["required"]
        # The 5 primary options requested by user
        for param in ["format", "algorithm", "sensitivity", "cut_threshold", "peak_prominence"]:
            self.assertIn("tooltip", req[param][1], f"Missing tooltip on {param}")
            self.assertTrue(len(req[param][1]["tooltip"]) > 5, f"Tooltip on {param} is too short")

    def test_node_outputs(self):
        self.assertEqual(SmartVideoSplitter.RETURN_TYPES, ("SMART_VIDEO_STREAM", "AUDIO", "INT"))
        self.assertEqual(SmartVideoSplitter.RETURN_NAMES, ("视频流", "音频", "帧数"))
        self.assertEqual(SmartVideoSplitter.FUNCTION, "process")
        self.assertEqual(SmartVideoSplitter.CATEGORY, "xiheha-工具箱/视频")

    def test_registration_in_init(self):
        import ast
        from pathlib import Path
        init_path = Path(__file__).resolve().parents[1] / "__init__.py"
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        class_mappings = {}
        display_mappings = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "NODE_CLASS_MAPPINGS" and isinstance(node.value, ast.Dict):
                            for k, v in zip(node.value.keys, node.value.values):
                                if isinstance(k, ast.Constant):
                                    class_mappings[k.value] = getattr(v, "id", None)
                        elif target.id == "NODE_DISPLAY_NAME_MAPPINGS" and isinstance(node.value, ast.Dict):
                            for k, v in zip(node.value.keys, node.value.values):
                                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                                    display_mappings[k.value] = v.value
        self.assertIn("XH_SmartVideoSplitter", class_mappings)
        self.assertEqual(class_mappings["XH_SmartVideoSplitter"], "SmartVideoSplitter")
        self.assertIn("XH_SmartVideoSplitter", display_mappings)
        self.assertEqual(display_mappings["XH_SmartVideoSplitter"], "智能视频分割器")

    def test_validate_inputs(self):
        # Empty or "none"
        self.assertEqual(SmartVideoSplitter.VALIDATE_INPUTS(""), "请先选择或上传视频文件。")
        self.assertEqual(SmartVideoSplitter.VALIDATE_INPUTS("none"), "请先选择或上传视频文件。")
        self.assertEqual(SmartVideoSplitter.VALIDATE_INPUTS(None), "请先选择或上传视频文件。")

        # Non-existent file
        res = SmartVideoSplitter.VALIDATE_INPUTS("non_existent_12345.mp4")
        self.assertIsInstance(res, str)
        self.assertIn("不存在", res)

        # Existing file (mock exists_annotated_filepath)
        from unittest.mock import patch
        with patch.object(folder_paths, "exists_annotated_filepath", return_value=True):
            self.assertTrue(SmartVideoSplitter.VALIDATE_INPUTS("my_video.mp4"))

    def test_splitter_state_includes_video_and_restoration(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the frontend state regression test")
        module_uri = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "web", "features", "smart-video-splitter", "state.js")
        ).replace("\\", "/")
        script = f"""
            import {{ parseSplitterState, serializeSplitterState }} from 'file:///{module_uri}';
            const state = parseSplitterState('{{"split_mode":"exact","target_duration":8,"video":"sub/test.mp4"}}');
            if (state.video !== 'sub/test.mp4' || state.split_mode !== 'exact') throw new Error('state restore failed');
            const restored = JSON.parse(serializeSplitterState(state));
            if (restored.video !== 'sub/test.mp4' || restored.target_duration !== 8) throw new Error('state serialization failed');
        """
        result = subprocess.run([node, "--input-type=module", "--eval", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)



class TestDimensionCalculation(unittest.TestCase):
    """Verify target_size aspect ratio, overrides and downscale ratio alignment."""

    def test_target_size_defaults(self):
        # width=0, height=0 -> unchanged rounded to multiple of 8
        w, h = target_size(1920, 1080, 0, 0, downscale_ratio=8)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

    def test_target_size_custom_height(self):
        # 1920x1080 (16:9), height=540 -> width should be 960, height aligned to 8 is 544
        w, h = target_size(1920, 1080, 0, 540, downscale_ratio=8)
        self.assertEqual(w, 960)
        self.assertEqual(h, 544)

    def test_target_size_custom_width(self):
        # 1920x1080, width=960 -> height should be 540 aligned to 8 is 544
        w, h = target_size(1920, 1080, 960, 0, downscale_ratio=8)
        self.assertEqual(w, 960)
        self.assertEqual(h, 544)

    def test_target_size_both_custom(self):
        w, h = target_size(1920, 1080, 720, 720, downscale_ratio=8)
        self.assertEqual(w, 720)
        self.assertEqual(h, 720)


class TestSceneDetectionMetrics(unittest.TestCase):
    """Verify algorithms on synthetic test frames."""

    def setUp(self):
        # Identical white frame
        self.white_frame1 = np.full((128, 128, 3), 255, dtype=np.uint8)
        self.white_frame2 = np.full((128, 128, 3), 255, dtype=np.uint8)
        # Black frame
        self.black_frame = np.zeros((128, 128, 3), dtype=np.uint8)
        # Random frames
        np.random.seed(42)
        self.noise1 = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)
        self.noise2 = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)

    def test_identical_frames_score_zero(self):
        self.assertAlmostEqual(compute_hsv_diff(self.white_frame1, self.white_frame2), 0.0, places=2)
        self.assertAlmostEqual(compute_ssim_diff(self.white_frame1, self.white_frame2), 0.0, places=2)
        self.assertAlmostEqual(compute_edge_diff(self.white_frame1, self.white_frame2), 0.0, places=2)
        self.assertAlmostEqual(compute_frame_diff(self.white_frame1, self.white_frame2), 0.0, places=2)
        self.assertAlmostEqual(compute_phash_diff(self.white_frame1, self.white_frame2), 0.0, places=2)
        self.assertAlmostEqual(compute_cut_score(self.white_frame1, self.white_frame2, "智能混合检测（推荐）"), 0.0, places=2)

    def test_contrasting_frames_score_high(self):
        # White to black is a massive visual transition
        ssim_d = compute_ssim_diff(self.white_frame1, self.black_frame)
        frame_d = compute_frame_diff(self.white_frame1, self.black_frame)
        self.assertGreater(ssim_d, 0.7)
        self.assertGreater(frame_d, 0.7)

    def test_different_algorithms(self):
        algos = ["智能混合检测（推荐）", "Content 内容变化", "HSV 直方图", "SSIM 结构变化", "Frame Difference 帧差", "Perceptual Hash 感知哈希"]
        for algo in algos:
            score = compute_cut_score(self.noise1, self.noise2, algo)
            self.assertTrue(0.0 <= score <= 1.0, f"Algorithm {algo} produced out of bound score {score}")


class TestCandidateSelection(unittest.TestCase):
    """Verify priority rules for choosing cut points."""

    def test_strong_cut_preferred_closest_to_target(self):
        # Two strong cut candidates
        candidates = [
            {"frame": 130, "score": 0.88, "prominence": 0.3, "is_strong": True, "dist_to_target": 20},
            {"frame": 148, "score": 0.82, "prominence": 0.25, "is_strong": True, "dist_to_target": 2},
        ]
        target_frame = 150
        cut, score, cut_type = select_best_cut(candidates, target_frame, 120, 180)
        # Should pick frame 148 because it is closest to target 150 despite 130 having higher score
        self.assertEqual(cut, 148)
        self.assertEqual(cut_type, "strong_scene")

    def test_fallback_when_no_candidates(self):
        target_frame = 150
        cut, score, cut_type = select_best_cut([], target_frame, 120, 180)
        self.assertEqual(cut, 150)
        self.assertEqual(score, 0.0)
        self.assertEqual(cut_type, "target_fallback")


class TestExactModeSegmentation(unittest.TestCase):
    """Verify exact mode frame slicing and non-overlapping interval continuity."""

    def test_exact_intervals_continuous(self):
        # 100 frames total, fps=10, target=2.5s -> 25 frames per segment
        segs = split_video_exact(total_frames=100, effective_fps=10.0, target_duration=2.5)
        self.assertEqual(len(segs), 4)

        # Check [start_frame, end_frame) left-closed right-open continuity
        for i in range(len(segs)):
            self.assertEqual(segs[i]["start_frame"], i * 25)
            self.assertEqual(segs[i]["end_frame"], (i + 1) * 25)
            self.assertEqual(segs[i]["frame_count"], 25)
            self.assertEqual(segs[i]["cut_type"], "exact")

    def test_exact_tail_remainder_preserved(self):
        # 105 frames total, 25 per segment -> 4 full segments (0-100) + 1 tail segment (100-105)
        segs = split_video_exact(total_frames=105, effective_fps=10.0, target_duration=2.5)
        self.assertEqual(len(segs), 5)
        self.assertEqual(segs[-1]["start_frame"], 100)
        self.assertEqual(segs[-1]["end_frame"], 105)
        self.assertEqual(segs[-1]["frame_count"], 5)
        self.assertEqual(segs[-1]["cut_type"], "exact_tail")
        # Sum of all segment frame_count must equal total_frames exactly
        self.assertEqual(sum(s["frame_count"] for s in segs), 105)


class TestNodeCacheIsolation(unittest.TestCase):
    """Verify node cache directories are isolated and clean_node_cache touches only its own dir."""

    def test_cache_directories_independent(self):
        dir_a = get_node_cache_dir("node_123")
        dir_b = get_node_cache_dir("node_456")
        self.assertNotEqual(dir_a, dir_b)
        self.assertTrue(dir_a.endswith("node_123"))
        self.assertTrue(dir_b.endswith("node_456"))

    def test_clean_only_affects_current_node(self):
        from unittest.mock import patch

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.object(folder_paths, "get_temp_directory", return_value=temporary.name):
            dir_a = clean_node_cache("test_node_a")
            dir_b = clean_node_cache("test_node_b")

            # Create dummy segment files in both
            file_a = os.path.join(dir_a, "segment_0001.mp4")
            file_b = os.path.join(dir_b, "segment_0001.mp4")
            with open(file_a, "w") as f:
                f.write("a")
            with open(file_b, "w") as f:
                f.write("b")

            self.assertTrue(os.path.isfile(file_a))
            self.assertTrue(os.path.isfile(file_b))

            # Re-clean node A: file A must be removed, file B must still exist!
            clean_node_cache("test_node_a")
            self.assertFalse(os.path.isfile(file_a))
            self.assertTrue(os.path.isfile(file_b))


class TestAudioFallback(unittest.TestCase):
    """Verify audio retrieval handles missing or non-audio files gracefully."""

    def test_dummy_audio_structure(self):
        audio = get_lazy_audio("non_existent_file.mp4")
        self.assertIn("waveform", audio)
        self.assertIn("sample_rate", audio)
        self.assertIsInstance(audio["waveform"], torch.Tensor)
        self.assertEqual(audio["sample_rate"], 44100)


class TestFrontendTooltipIntegration(unittest.TestCase):
    """Verify standalone tooltip stylesheet, custom tooltip preservation switch, and native tooltips."""

    def test_frontend_tooltip_definitions_and_switch(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        adapter = (root / "web" / "nodes" / "smart-video-splitter.js").read_text(encoding="utf-8")
        controller = (root / "web" / "features" / "smart-video-splitter" / "controller.js").read_text(encoding="utf-8")
        self.assertIn("export const ENABLE_CUSTOM_TOOLTIP = false", adapter)
        self.assertIn("registerCustomTooltip(node", controller)
        self.assertIn("hoverDelay: 1000", controller)

    def test_standalone_tooltip_stylesheet(self):
        standalone_css_path = os.path.join(os.path.dirname(__file__), "..", "web", "styles", "tooltip.css")
        main_css_path = os.path.join(os.path.dirname(__file__), "..", "web", "toolkit.css")

        self.assertTrue(os.path.isfile(standalone_css_path), "web/styles/tooltip.css must exist as independent stylesheet")

        with open(standalone_css_path, "r", encoding="utf-8") as f:
            tooltip_css = f.read()
        with open(main_css_path, "r", encoding="utf-8") as f:
            main_css = f.read()
        # Standalone stylesheet has tooltip rules
        self.assertIn(".xh-tooltip", tooltip_css)
        self.assertIn(".xh-tooltip.visible", tooltip_css)

        # The style manifest leaves optional Tooltip CSS on-demand.
        self.assertNotIn(".xh-tooltip", main_css)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(__file__), "..", "web", "shared", "styles.js")))

    def test_python_native_tooltips_multiline(self):
        inputs = SmartVideoSplitter.INPUT_TYPES()
        req = inputs["required"]
        for param in ["format", "algorithm", "sensitivity", "cut_threshold", "peak_prominence"]:
            tooltip = req[param][1]["tooltip"]
            self.assertIn("\n", tooltip, f"{param} tooltip should have multi-line formatting for native view")
            self.assertTrue(tooltip.startswith("【"), f"{param} tooltip should start with clear section header")

    def test_mutual_exclusion_logic_exported_and_isolated(self):
        runtime_path = os.path.join(
            os.path.dirname(__file__), "..", "web", "shared", "tooltip", "runtime.js"
        )
        with open(runtime_path, "r", encoding="utf-8") as f:
            runtime = f.read()
        self.assertIn("registeredNodes.get(node)", runtime)
        self.assertIn("for (const widget of node.widgets)", runtime)
        self.assertIn("widget.__xhOrigTooltip", runtime)


class TestFrontendNodeSizing(unittest.TestCase):
    """Verify automatic layout never shrinks a manually expanded splitter node."""

    def test_minimum_size_and_manual_expansion_are_preserved(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the frontend sizing regression test")

        module_uri = (
            os.path.join(os.path.dirname(__file__), "..", "web", "nodes", "smart-video-splitter-size.js")
        )
        module_uri = os.path.abspath(module_uri).replace("\\", "/")
        script = f"""
            import {{ MIN_WIDTH, MIN_HEIGHT, preserveNodeSize }} from 'file:///{module_uri}';
            const assert = (condition, message) => {{ if (!condition) throw new Error(message); }};
            assert(MIN_WIDTH === 350, `expected 350px minimum width, got ${{MIN_WIDTH}}`);
            assert(MIN_HEIGHT === 700, `expected 700px minimum height, got ${{MIN_HEIGHT}}`);
            assert(JSON.stringify(preserveNodeSize([640, 900], [350, 700])) === '[640,900]', 'manual expansion was shrunk');
            assert(JSON.stringify(preserveNodeSize([200, 500], [300, 650])) === '[350,700]', 'minimum size was not enforced');
            assert(JSON.stringify(preserveNodeSize([400, 800], [520, 860])) === '[520,860]', 'computed expansion was not applied');
        """
        result = subprocess.run(
            [node, "--input-type=module", "--eval", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestFrontendVideoStatePersistence(unittest.TestCase):
    """Verify video state restoration and URL building logic."""

    def test_video_view_url_and_state_restore_simulation(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for frontend persistence simulation test")

        module_uri = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "web", "features", "smart-video-splitter", "state.js")
        ).replace("\\", "/")
        script = f"""
        import {{ parseSplitterState, videoViewPath }} from 'file:///{module_uri}';
        const assert = (condition, message) => {{ if (!condition) throw new Error(message); }};
        assert(videoViewPath('test.mp4') === '/view?filename=test.mp4&type=input', 'standard filename failed');
        assert(videoViewPath('sub/test.mp4') === '/view?filename=test.mp4&type=input&subfolder=sub', 'subfolder failed');
        assert(videoViewPath('nested/folder/test.mp4') === '/view?filename=test.mp4&type=input&subfolder=nested%2Ffolder', 'nested subfolder failed');
        assert(videoViewPath('win\\\\sub\\\\test.mp4') === '/view?filename=test.mp4&type=input&subfolder=win%2Fsub', 'windows path failed');
        const restored = parseSplitterState(JSON.stringify({{ video: 'restored.mp4', split_mode: 'fuzzy' }}), 'fallback.mp4');
        assert(restored.video === 'restored.mp4', 'serialized video was not restored');
        assert(parseSplitterState('{{}}', 'fallback.mp4').video === 'fallback.mp4', 'widget fallback failed');
        """
        result = subprocess.run(
            [node, "--input-type=module", "--eval", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
