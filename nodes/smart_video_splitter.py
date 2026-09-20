"""Smart Video Splitter node implementation."""

from __future__ import annotations

import json
import os
from typing import Any

import folder_paths

try:
    from ..core.scene_detector import split_video_exact, split_video_fuzzy
    from ..core.video_cutter import (
        clean_node_cache,
        cut_and_cache_segments,
        get_node_cache_dir,
    )
    from ..core.video_meta import (
        DIMMAX,
        LOAD_FORMATS,
        get_input_video_files,
        get_lazy_audio,
        get_video_metadata,
        target_size,
    )
except (ImportError, ValueError):
    from core.scene_detector import split_video_exact, split_video_fuzzy
    from core.video_cutter import (
        clean_node_cache,
        cut_and_cache_segments,
        get_node_cache_dir,
    )
    from core.video_meta import (
        DIMMAX,
        LOAD_FORMATS,
        get_input_video_files,
        get_lazy_audio,
        get_video_metadata,
        target_size,
    )

ALGORITHMS = [
    "智能混合检测（推荐）",
    "Content 内容变化",
    "HSV 直方图",
    "SSIM 结构变化",
    "Frame Difference 帧差",
    "Perceptual Hash 感知哈希",
]


class SmartVideoSplitter:
    """智能视频分割器：无输入端口，自动将视频切分为多个缓存片段并输出 SMART_VIDEO_STREAM。"""

    @classmethod
    def INPUT_TYPES(cls):
        files = get_input_video_files()
        return {
            "required": {
                "video": (files if files else ["none"], {
                    "tooltip": "【视频源文件】\n选择放置在 input 目录的待分割视频，或点击面板中的「上传视频」上传本地视频。"
                }),
                "force_rate": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 120.0, "step": 1.0,
                    "tooltip": "【强制帧率 (FPS)】\n强制将切片视频重采样为指定帧率。设为 0 时保持源视频原生帧率不变。"
                }),
                "custom_width": ("INT", {
                    "default": 0, "min": 0, "max": DIMMAX, "step": 8,
                    "tooltip": "【自定义宽度 (px)】\n输出片段的目标宽度。设为 0 时根据目标高度和原视频比例自动缩放并对齐倍数。"
                }),
                "custom_height": ("INT", {
                    "default": 540, "min": 0, "max": DIMMAX, "step": 8,
                    "tooltip": "【自定义高度 (px)】\n输出片段的目标高度（默认540）。若宽高均设为 0，则保持源视频原生分辨率。"
                }),
                "format": (list(LOAD_FORMATS.keys()), {
                    "default": "AnimatedDiff",
                    "tooltip": (
                        "【模型格式规范】\n"
                        "选择目标生成模型生态。系统将按目标模型规格自动计算倍数对齐（8x/16x/32x）与比例约束，对切片进行重采样与智能裁切。\n"
                        "• AnimatedDiff: 标准 8 像素对齐，兼顾通用 SD1.5 / SDXL\n"
                        "• Mochi: 16 像素降采样对齐，适配空间注意力机制\n"
                        "• LTX-Video: 32 像素重采样对齐，支持极高空间压缩比\n"
                        "• Wan (万相): Wan2.1 系列特化编码与补帧适配\n"
                        "• 原尺寸/自定义: 保持原始宽高比或严格按填写的自定义宽高输出"
                    ),
                }),
                "split_mode": (["fuzzy", "exact"], {
                    "default": "fuzzy",
                    "tooltip": "【分段模式】\n• fuzzy (模糊): 动态检测镜头切点，兼顾目标时长与场景转场完整度\n• exact (精确): 按目标时长严格切分为等长区间，保留尾段余数"
                }),
                "fuzzy_min": ("FLOAT", {
                    "default": 4.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": "【模糊分段最短时长 (秒)】\n允许切分的最小时间片段长度，系统绝不生成低于该时长的碎片。"
                }),
                "target_duration": ("FLOAT", {
                    "default": 5.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": "【目标分段时长 (秒)】\n期望的核心分段时长。模糊模式下优先就近落刀，精确模式下为严格固定切片时长。"
                }),
                "fuzzy_max": ("FLOAT", {
                    "default": 6.0, "min": 3.0, "max": 15.0, "step": 0.1,
                    "tooltip": "【模糊分段最长时长 (秒)】\n单个片段的最大时间上限，即使未检测到明显切镜也会在此处平滑收刀。"
                }),
                "algorithm": (ALGORITHMS, {
                    "default": "智能混合检测（推荐）",
                    "tooltip": (
                        "【镜头转场检测算法】\n"
                        "用于识别镜头切换、场景跳切与转场突变的核心比对模型：\n"
                        "• 智能混合检测（推荐）: 结合 HSV 色相与 Content 纹理双轨检测，抗晃动噪点，切镜准确率最高\n"
                        "• Content 内容变化: 基于亮度差与边缘纹理突变检测硬切，对光影闪变敏感\n"
                        "• HSV 直方图: 分析色相与明度分布，适合捕获色彩风格剧变\n"
                        "• SSIM 结构变化: 计算画面结构相似性衰减，擅长检测大幅构图重组\n"
                        "• Frame Difference 帧差: 逐像素绝对差值统计，运算速度极快，适合平缓视频\n"
                        "• Perceptual Hash 感知哈希: 基于频域指纹比对宏观视觉特征，对微小运动鲁棒"
                    ),
                }),
                "sensitivity": ("FLOAT", {
                    "default": 0.60, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【检测灵敏度】\n"
                        "控制镜头突变判定的全局容差。默认值 0.60（范围 0.00 ~ 1.00）。\n"
                        "• 调高 (如 0.70 ~ 0.90): 更敏锐，微小运镜晃动、快速摇移或短促跳切均会被切分，分段更碎\n"
                        "• 调低 (如 0.30 ~ 0.50): 更保守，仅在发生彻底、明显的场景转变时才切分，避免过度切碎"
                    ),
                }),
                "cut_threshold": ("FLOAT", {
                    "default": 0.55, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【切镜阈值】\n"
                        "判定两帧之间发生镜头突变的最低绝对分数门槛。默认值 0.55（范围 0.00 ~ 1.00）。\n"
                        "• 调高 (如 0.70+): 要求极其强烈的视觉反差（如黑屏过渡、不同场景硬切），减少切片数量\n"
                        "• 调低 (如 0.35 ~ 0.45): 对同机位微小转场、淡入淡出更易识别，保留更多细微切点"
                    ),
                }),
                "peak_prominence": ("FLOAT", {
                    "default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": (
                        "【显著度阈值】\n"
                        "局部切镜突变峰值与相邻两帧背景基准线的最小落差要求。默认值 0.12（范围 0.00 ~ 1.00）。\n"
                        "• 核心作用: 有效过滤手持跟拍晃动、镜头快速推拉摇移 (Pan/Zoom) 引起的连续高分误判\n"
                        "• 调高数值: 消除连续运镜造成的假转场，只在出现孤立显著突变时落刀\n"
                        "• 调低数值: 保留密集快切、快节奏蒙太奇等紧凑切镜点"
                    ),
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "splitter_state": "STRING",
            },
        }

    RETURN_TYPES = ("SMART_VIDEO_STREAM", "AUDIO", "INT")
    RETURN_NAMES = ("视频流", "音频", "帧数")
    FUNCTION = "process"
    CATEGORY = "xiheha-工具箱/视频"

    def process(
        self,
        video: str,
        force_rate: float = 0.0,
        custom_width: int = 0,
        custom_height: int = 540,
        format: str = "AnimatedDiff",
        split_mode: str = "fuzzy",
        fuzzy_min: float = 4.0,
        target_duration: float = 5.0,
        fuzzy_max: float = 6.0,
        algorithm: str = "智能混合检测（推荐）",
        sensitivity: float = 0.60,
        cut_threshold: float = 0.55,
        peak_prominence: float = 0.12,
        unique_id: str | int | None = None,
        splitter_state: str = "{}",
        **kwargs: Any,
    ) -> tuple[dict[str, Any], Any, int]:
        if not video or video == "none":
            raise ValueError("请先选择或上传视频文件。")

        cleaned_video = video.strip().strip('"')
        video_path = folder_paths.get_annotated_filepath(cleaned_video)
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"视频文件不存在: {cleaned_video}")

        node_id = str(unique_id) if unique_id is not None else "default"
        cache_dir = get_node_cache_dir(node_id)
        manifest_path = os.path.join(cache_dir, "manifest.json")

        meta = get_video_metadata(video_path)
        effective_fps = float(force_rate) if force_rate > 0 else float(meta["fps"])

        fmt_config = LOAD_FORMATS.get(format, {})
        downscale_ratio = fmt_config.get("dim", (8,))[0] if "dim" in fmt_config else 8
        out_w, out_h = target_size(meta["width"], meta["height"], custom_width, custom_height, downscale_ratio)

        # Ensure valid constraint: min <= target <= max
        f_min = min(float(fuzzy_min), float(target_duration))
        f_target = float(target_duration)
        f_max = max(float(fuzzy_max), float(target_duration))

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

        # Check whether an existing manifest can be reused
        stream_data = None
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                src = cached.get("source", {})
                out = cached.get("output", {})
                sett = cached.get("settings", {})
                if (
                    src.get("path") == video_path
                    and out.get("width") == out_w
                    and out.get("height") == out_h
                    and out.get("fps") == effective_fps
                    and sett.get("split_mode") == split_mode
                    and sett.get("target_duration") == f_target
                    and all(os.path.isfile(s.get("path", "")) for s in cached.get("segments", []))
                ):
                    stream_data = cached
            except Exception:
                stream_data = None

        if stream_data is None:
            total_frames = meta["frame_count"]
            if split_mode == "exact":
                segments_plan = split_video_exact(
                    total_frames=total_frames,
                    effective_fps=effective_fps,
                    target_duration=f_target,
                )
            else:
                segments_plan = split_video_fuzzy(
                    video_path=video_path,
                    total_frames=total_frames,
                    effective_fps=effective_fps,
                    min_duration=f_min,
                    target_duration=f_target,
                    max_duration=f_max,
                    algorithm=algorithm,
                    sensitivity=sensitivity,
                    cut_threshold=cut_threshold,
                    peak_prominence=peak_prominence,
                )

            stream_data = cut_and_cache_segments(
                node_id=node_id,
                source_meta=meta,
                segments_plan=segments_plan,
                output_w=out_w,
                output_h=out_h,
                effective_fps=effective_fps,
                model_format=format,
                split_mode=split_mode,
                settings=settings,
            )

        audio = get_lazy_audio(video_path, start_time=0.0, duration=meta["duration"])
        total_output_frames = sum(s["frame_count"] for s in stream_data.get("segments", []))

        return (stream_data, audio, total_output_frames)
