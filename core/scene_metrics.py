"""Frame descriptors and motion-compensation metrics for scene detection."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


SMART_DETECTION = "智能自适应检测（推荐）"
FAST_DETECTION = "快速内容检测"
HIGH_MOTION_DETECTION = "高运动抑制检测"

DETECTION_MODES = (
    SMART_DETECTION,
    FAST_DETECTION,
    HIGH_MOTION_DETECTION,
)

REMOVED_DETECTION_MODES = frozenset(
    {
        "智能混合检测（推荐）",
        "Content 内容变化",
        "HSV 直方图",
        "SSIM 结构变化",
        "Frame Difference 帧差",
        "Perceptual Hash 感知哈希",
    }
)


@dataclass(frozen=True)
class FrameDescriptor:
    """Compact, motion-tolerant representation of one analysis frame."""

    hsv_hist: np.ndarray
    luma_hist: np.ndarray
    edge_hist: np.ndarray
    phash: np.ndarray
    luma: float


@dataclass(frozen=True)
class DescriptorDifference:
    """Normalized differences between two frame descriptors."""

    hsv: float
    luma_hist: float
    edge: float
    phash: float
    luma: float
    score: float


@dataclass(frozen=True)
class MotionExplanation:
    """How much of an apparent change is explained by coherent optical flow."""

    explained: float
    coherence: float
    raw_residual: float
    compensated_residual: float


def _normalized_hist(values: np.ndarray, bins: int, value_range: tuple[float, float]) -> np.ndarray:
    hist = cv2.calcHist([values], [0], None, [bins], list(value_range))
    cv2.normalize(hist, hist, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
    return hist.astype(np.float32)


def describe_frame(frame: np.ndarray) -> FrameDescriptor:
    """Build reusable descriptors without retaining the full frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    hsv_hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hsv_hist, hsv_hist, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)

    luma_hist = _normalized_hist(gray, 32, (0, 256))

    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    edge_hist = _normalized_hist(np.clip(magnitude, 0, 1024).astype(np.float32), 16, (0, 1024))

    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct_low = cv2.dct(small)[:8, :8].reshape(-1)
    ac_values = dct_low[1:]
    phash = ac_values > float(np.median(ac_values))

    return FrameDescriptor(
        hsv_hist=hsv_hist.astype(np.float32),
        luma_hist=luma_hist,
        edge_hist=edge_hist,
        phash=phash,
        luma=float(np.mean(gray) / 255.0),
    )


def compare_descriptors(first: FrameDescriptor, second: FrameDescriptor) -> DescriptorDifference:
    """Return calibrated descriptor differences in the range [0.0, 1.0]."""
    hsv_diff = float(np.clip(cv2.compareHist(first.hsv_hist, second.hsv_hist, cv2.HISTCMP_BHATTACHARYYA), 0.0, 1.0))
    luma_hist_diff = float(
        np.clip(cv2.compareHist(first.luma_hist, second.luma_hist, cv2.HISTCMP_BHATTACHARYYA), 0.0, 1.0)
    )
    edge_diff = float(
        np.clip(cv2.compareHist(first.edge_hist, second.edge_hist, cv2.HISTCMP_BHATTACHARYYA), 0.0, 1.0)
    )
    phash_diff = float(np.clip(np.count_nonzero(first.phash != second.phash) / 63.0 * 2.0, 0.0, 1.0))
    luma_diff = float(np.clip(abs(first.luma - second.luma) * 2.0, 0.0, 1.0))

    score = (
        phash_diff * 0.50
        + hsv_diff * 0.25
        + luma_hist_diff * 0.15
        + edge_diff * 0.08
        + luma_diff * 0.02
    )
    return DescriptorDifference(
        hsv=hsv_diff,
        luma_hist=luma_hist_diff,
        edge=edge_diff,
        phash=phash_diff,
        luma=luma_diff,
        score=float(np.clip(score, 0.0, 1.0)),
    )


def should_check_optical_flow(
    mode: str,
    difference: DescriptorDifference,
    cut_threshold: float,
) -> bool:
    """Apply dense flow only to plausible or structurally ambiguous cuts."""
    if mode == FAST_DETECTION:
        return False
    if mode == HIGH_MOTION_DETECTION:
        gate = max(0.16, cut_threshold * 0.34)
        return difference.score >= gate or difference.phash >= 0.30
    gate = max(0.28, cut_threshold * 0.58)
    return difference.score >= gate or (difference.phash >= 0.55 and difference.hsv < 0.18)


def compute_motion_explanation(previous: np.ndarray, current: np.ndarray) -> MotionExplanation:
    """Estimate whether coherent motion can explain the apparent frame change."""
    prev_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        0.5,
        3,
        15,
        3,
        5,
        1.2,
        0,
    )

    height, width = prev_gray.shape
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    map_x = grid_x + flow[..., 0]
    map_y = grid_y + flow[..., 1]
    valid = (map_x >= 0) & (map_x <= width - 1) & (map_y >= 0) & (map_y <= height - 1)

    raw_residual = float(np.mean(cv2.absdiff(prev_gray, curr_gray)) / 255.0)
    if np.count_nonzero(valid) < max(64, int(height * width * 0.25)):
        return MotionExplanation(0.0, 0.0, raw_residual, raw_residual)

    warped_current = cv2.remap(
        curr_gray,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT101,
    )
    compensated_residual = float(
        np.mean(np.abs(prev_gray.astype(np.float32)[valid] - warped_current.astype(np.float32)[valid])) / 255.0
    )
    improvement = float(np.clip((raw_residual - compensated_residual) / max(raw_residual, 1e-6), 0.0, 1.0))

    smooth_flow = cv2.GaussianBlur(flow, (5, 5), 0)
    roughness = np.linalg.norm(flow - smooth_flow, axis=2)
    magnitude = np.linalg.norm(flow, axis=2)
    coherence = float(
        np.clip(1.0 - np.median(roughness) / max(0.25, float(np.median(magnitude)) + 0.25), 0.0, 1.0)
    )
    explained = float(np.clip(improvement * (0.45 + 0.55 * coherence), 0.0, 1.0))
    return MotionExplanation(explained, coherence, raw_residual, compensated_residual)


def apply_motion_suppression(score: float, mode: str, motion: MotionExplanation) -> float:
    """Reduce only changes that optical flow explains as coherent motion."""
    strength = 0.92 if mode == HIGH_MOTION_DETECTION else 0.80
    explained = min(1.0, motion.explained * 1.8)
    return float(np.clip(score * (1.0 - strength * explained), 0.0, 1.0))
