"""Scene detection, sliding window scanning, peak detection, and segmentation logic."""

from __future__ import annotations

from typing import Any, Callable
import cv2
import numpy as np


def resize_frame_for_analysis(frame: np.ndarray, max_dim: int = 256) -> np.ndarray:
    """Downscale frame keeping aspect ratio to minimize CPU/memory overhead."""
    h, w = frame.shape[:2]
    if max(h, w) <= max_dim:
        return frame
    scale = max_dim / float(max(h, w))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)


def compute_hsv_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute normalized 2D HSV histogram difference in [0.0, 1.0]."""
    hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
    hist1 = cv2.calcHist([hsv1], [0, 1], None, [30, 32], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    # Correlation is in [-1.0, 1.0], convert to difference in [0.0, 1.0]
    diff = (1.0 - float(corr)) / 2.0
    return float(np.clip(diff, 0.0, 1.0))


def compute_ssim_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute structural similarity index difference in [0.0, 1.0]."""
    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY).astype(np.float32)

    c1 = 6.5025
    c2 = 58.5225

    mu1 = cv2.GaussianBlur(g1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(g2, (11, 11), 1.5)

    mu1_sq = mu1 * mu1
    mu2_sq = mu2 * mu2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(g1 * g1, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(g2 * g2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(g1 * g2, (11, 11), 1.5) - mu1_mu2

    num = (2 * mu1_mu2 + c1) * (2 * sigma12 + c2)
    den = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    ssim_map = num / (den + 1e-6)
    ssim_val = float(np.mean(ssim_map))
    # SSIM is in [-1.0, 1.0], difference is in [0.0, 1.0]
    return float(np.clip(1.0 - max(0.0, ssim_val), 0.0, 1.0))


def compute_edge_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute Sobel edge difference in [0.0, 1.0]."""
    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    e1 = cv2.Sobel(g1, cv2.CV_32F, 1, 1, ksize=3)
    e2 = cv2.Sobel(g2, cv2.CV_32F, 1, 1, ksize=3)
    diff = float(np.mean(np.abs(e1 - e2)) / 255.0)
    return float(np.clip(diff * 2.0, 0.0, 1.0))


def compute_frame_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute normalized pixel absolute difference in [0.0, 1.0]."""
    g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    diff = float(np.mean(cv2.absdiff(g1, g2)) / 255.0)
    return float(np.clip(diff * 2.5, 0.0, 1.0))


def compute_phash_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute perceptual hash distance difference in [0.0, 1.0]."""
    def _phash(img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        dct = cv2.dct(small)
        dct_low = dct[:8, :8]
        med = float(np.median(dct_low))
        return dct_low > med

    h1 = _phash(frame1)
    h2 = _phash(frame2)
    dist = float(np.count_nonzero(h1 != h2)) / 64.0
    return float(np.clip(dist * 2.0, 0.0, 1.0))


def compute_content_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute content change metric combining color and luminance shifts."""
    hsv_d = compute_hsv_diff(frame1, frame2)
    frame_d = compute_frame_diff(frame1, frame2)
    return float(np.clip(0.6 * hsv_d + 0.4 * frame_d, 0.0, 1.0))


def compute_cut_score(frame1: np.ndarray, frame2: np.ndarray, algorithm: str) -> float:
    """Compute cut score between two consecutive frames in [0.0, 1.0]."""
    algo = algorithm.strip().lower()
    if "hsv" in algo:
        return compute_hsv_diff(frame1, frame2)
    if "ssim" in algo:
        return compute_ssim_diff(frame1, frame2)
    if "edge" in algo:
        return compute_edge_diff(frame1, frame2)
    if "frame" in algo or "帧差" in algo:
        return compute_frame_diff(frame1, frame2)
    if "hash" in algo or "哈希" in algo:
        return compute_phash_diff(frame1, frame2)
    if "content" in algo or "内容" in algo:
        return compute_content_diff(frame1, frame2)

    # Default: 智能混合检测 (smart_mix)
    # cut_score = hsv_diff * 0.45 + ssim_diff * 0.35 + edge_diff * 0.20
    hsv_s = compute_hsv_diff(frame1, frame2)
    ssim_s = compute_ssim_diff(frame1, frame2)
    edge_s = compute_edge_diff(frame1, frame2)
    score = hsv_s * 0.45 + ssim_s * 0.35 + edge_s * 0.20
    return float(np.clip(score, 0.0, 1.0))


class FrameReader:
    """On-demand frame reader using OpenCV VideoCapture with downscaling."""
    def __init__(self, video_path: str, max_dim: int = 256):
        self.video_path = video_path
        self.max_dim = max_dim
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Unable to open video: {video_path}")
        self.current_idx = -1

    def get_frame(self, frame_idx: int) -> np.ndarray | None:
        if frame_idx != self.current_idx + 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            self.current_idx = frame_idx - 1

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None
        self.current_idx = frame_idx
        return resize_frame_for_analysis(frame, self.max_dim)

    def close(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def scan_window_cuts(
    reader: FrameReader,
    window_start_frame: int,
    window_end_frame: int,
    target_frame: int,
    algorithm: str,
    sensitivity: float,
    cut_threshold: float,
    peak_prominence: float,
    strong_cut_threshold: float = 0.75,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Scan frames in [window_start_frame, window_end_frame] to identify candidate scene cuts."""
    if window_end_frame <= window_start_frame:
        return []

    # Read previous boundary frame for diff
    prev_frame = reader.get_frame(max(0, window_start_frame - 1))
    if prev_frame is None:
        return []

    frame_indices: list[int] = []
    scores: list[float] = []

    for f_idx in range(window_start_frame, window_end_frame + 1):
        curr_frame = reader.get_frame(f_idx)
        if curr_frame is None:
            break
        score = compute_cut_score(prev_frame, curr_frame, algorithm)
        frame_indices.append(f_idx)
        scores.append(score)
        prev_frame = curr_frame
        if progress_callback:
            progress_callback(f_idx, window_end_frame)

    if not scores:
        return []

    scores_arr = np.array(scores, dtype=np.float32)
    med = float(np.median(scores_arr))
    mad = float(np.median(np.abs(scores_arr - med)))
    # Dynamic threshold: higher sensitivity lowers K
    k = max(0.5, 2.5 - 2.0 * float(sensitivity))
    adaptive_threshold = med + k * mad
    effective_thresh = max(0.20, min(0.95, 0.5 * cut_threshold + 0.5 * adaptive_threshold))

    candidates: list[dict[str, Any]] = []
    n = len(scores)

    for i in range(n):
        f_idx = frame_indices[i]
        score = scores[i]

        # Local peak prominence: compare against surrounding averages (up to 5 frames)
        left_slice = scores[max(0, i - 5):i]
        right_slice = scores[i + 1:min(n, i + 6)]
        left_avg = float(np.mean(left_slice)) if len(left_slice) > 0 else med
        right_avg = float(np.mean(right_slice)) if len(right_slice) > 0 else med
        prominence = score - max(left_avg, right_avg)

        is_strong = (score >= strong_cut_threshold) and (prominence >= peak_prominence)
        is_candidate = (score >= effective_thresh) and (prominence >= peak_prominence)

        if is_strong or is_candidate:
            candidates.append({
                "frame": f_idx,
                "score": round(score, 4),
                "prominence": round(prominence, 4),
                "is_strong": is_strong,
                "dist_to_target": abs(f_idx - target_frame),
            })

    return candidates


def select_best_cut(
    candidates: list[dict[str, Any]],
    target_frame: int,
    window_start: int,
    window_end: int,
) -> tuple[int, float, str]:
    """Select best cut from candidates according to priority rules."""
    if not candidates:
        return target_frame, 0.0, "target_fallback"

    strong_candidates = [c for c in candidates if c["is_strong"]]
    if strong_candidates:
        # Priority: multiple strong scene cuts -> choose one closest to target
        best_strong = min(strong_candidates, key=lambda c: (c["dist_to_target"], -c["score"]))
        return best_strong["frame"], best_strong["score"], "strong_scene"

    # Evaluate normal candidates: balance between cut_score and distance to TARGET
    span = max(1, window_end - window_start)
    best_candidate = min(
        candidates,
        key=lambda c: (
            (1.0 - c["score"]) * 0.4 + (c["dist_to_target"] / span) * 0.6
        )
    )
    return best_candidate["frame"], best_candidate["score"], "scene"


def split_video_fuzzy(
    video_path: str,
    total_frames: int,
    effective_fps: float,
    min_duration: float,
    target_duration: float,
    max_duration: float,
    algorithm: str,
    sensitivity: float,
    cut_threshold: float,
    peak_prominence: float,
    strong_cut_threshold: float = 0.75,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Execute fuzzy segmentation with sliding window detection and tail backtracking."""
    min_frames = max(1, int(round(min_duration * effective_fps)))
    target_frames = max(min_frames, int(round(target_duration * effective_fps)))
    max_frames = max(target_frames, int(round(max_duration * effective_fps)))

    # Short video handling
    if total_frames <= target_frames or total_frames <= min_frames:
        return [{
            "start_frame": 0,
            "end_frame": total_frames,
            "frame_count": total_frames,
            "start_time": 0.0,
            "end_time": round(total_frames / effective_fps, 3),
            "duration": round(total_frames / effective_fps, 3),
            "cut_score": 1.0,
            "cut_type": "single",
            "constraint_warning": (total_frames < min_frames),
        }]

    segments: list[dict[str, Any]] = []
    window_candidates_history: list[dict[str, Any]] = []

    with FrameReader(video_path) as reader:
        current_start = 0

        while current_start < total_frames:
            rem_frames = total_frames - current_start

            # If remaining frames are already within [min_frames, max_frames] or close, take all as last segment
            if rem_frames <= max_frames:
                warning = rem_frames < min_frames
                segments.append({
                    "start_frame": current_start,
                    "end_frame": total_frames,
                    "frame_count": rem_frames,
                    "start_time": round(current_start / effective_fps, 3),
                    "end_time": round(total_frames / effective_fps, 3),
                    "duration": round(rem_frames / effective_fps, 3),
                    "cut_score": 0.0,
                    "cut_type": "tail" if segments else "single",
                    "constraint_warning": warning,
                })
                break

            w_start = current_start + min_frames
            w_end = min(total_frames - 1, current_start + max_frames)
            target_cut = min(w_end, current_start + target_frames)

            def _step_cb(cur, tot):
                if progress_callback:
                    progress_callback("analyzing", cur, total_frames)

            candidates = scan_window_cuts(
                reader=reader,
                window_start_frame=w_start,
                window_end_frame=w_end,
                target_frame=target_cut,
                algorithm=algorithm,
                sensitivity=sensitivity,
                cut_threshold=cut_threshold,
                peak_prominence=peak_prominence,
                strong_cut_threshold=strong_cut_threshold,
                progress_callback=_step_cb,
            )

            cut_frame, cut_score, cut_type = select_best_cut(candidates, target_cut, w_start, w_end)

            # Check for tail conflict: if cut_frame leaves remaining frames < min_frames
            after_rem = total_frames - cut_frame
            constraint_warning = False

            if 0 < after_rem < min_frames:
                # Tail optimization: try to find an alternative cut in candidates that keeps after_rem >= min_frames
                valid_alt = None
                span = max(1, w_end - w_start)
                for alt in sorted(candidates, key=lambda c: abs(c["frame"] - target_cut)):
                    alt_rem = total_frames - alt["frame"]
                    if alt_rem >= min_frames or alt_rem == 0:
                        valid_alt = alt
                        break

                if valid_alt is not None:
                    cut_frame = valid_alt["frame"]
                    cut_score = valid_alt["score"]
                    cut_type = "strong_scene" if valid_alt["is_strong"] else "scene"
                else:
                    # If candidates don't have a valid alternative, try moving cut earlier if possible
                    earlier_cut = total_frames - min_frames
                    if w_start <= earlier_cut <= w_end:
                        cut_frame = earlier_cut
                        cut_score = 0.0
                        cut_type = "target_fallback"
                    else:
                        # Mathematically impossible to keep all >= min_frames
                        constraint_warning = True

            frame_len = cut_frame - current_start
            segments.append({
                "start_frame": current_start,
                "end_frame": cut_frame,
                "frame_count": frame_len,
                "start_time": round(current_start / effective_fps, 3),
                "end_time": round(cut_frame / effective_fps, 3),
                "duration": round(frame_len / effective_fps, 3),
                "cut_score": cut_score,
                "cut_type": cut_type,
                "constraint_warning": constraint_warning,
            })
            window_candidates_history.append({"start": current_start, "candidates": candidates, "cut": cut_frame})
            current_start = cut_frame

    return segments


def split_video_exact(
    total_frames: int,
    effective_fps: float,
    target_duration: float,
) -> list[dict[str, Any]]:
    """Execute exact frame-interval segmentation without scene detection."""
    seg_frames = max(1, int(round(target_duration * effective_fps)))
    segments: list[dict[str, Any]] = []

    curr = 0
    while curr < total_frames:
        nxt = min(curr + seg_frames, total_frames)
        frame_len = nxt - curr
        is_tail = (nxt == total_frames) and (frame_len < seg_frames) and (curr > 0)
        segments.append({
            "start_frame": curr,
            "end_frame": nxt,
            "frame_count": frame_len,
            "start_time": round(curr / effective_fps, 3),
            "end_time": round(nxt / effective_fps, 3),
            "duration": round(frame_len / effective_fps, 3),
            "cut_score": 1.0,
            "cut_type": "exact_tail" if is_tail else "exact",
            "constraint_warning": False,
        })
        curr = nxt

    return segments
