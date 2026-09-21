"""Scene detection, sliding window scanning, peak detection, and segmentation logic."""

from __future__ import annotations

from typing import Any, Callable
import cv2
import numpy as np

from .scene_metrics import (
    DETECTION_MODES,
    FrameDescriptor,
    apply_motion_suppression,
    compare_descriptors,
    compute_motion_explanation,
    describe_frame,
    should_check_optical_flow,
)


def resize_frame_for_analysis(frame: np.ndarray, max_dim: int = 256) -> np.ndarray:
    """Downscale frame keeping aspect ratio to minimize CPU/memory overhead."""
    h, w = frame.shape[:2]
    if max(h, w) <= max_dim:
        return frame
    scale = max_dim / float(max(h, w))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)


def compute_cut_score(
    frame1: np.ndarray,
    frame2: np.ndarray,
    algorithm: str,
    cut_threshold: float = 0.55,
) -> float:
    """Compute the new mode-aware hard-cut score for one adjacent frame pair."""
    if algorithm not in DETECTION_MODES:
        raise ValueError("旧检测算法已移除，请重新选择检测模式")
    difference = compare_descriptors(describe_frame(frame1), describe_frame(frame2))
    score = difference.score
    if should_check_optical_flow(algorithm, difference, cut_threshold):
        score = apply_motion_suppression(score, algorithm, compute_motion_explanation(frame1, frame2))
    return score


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


def _candidate(
    frame: int,
    score: float,
    target_frame: int,
    *,
    is_strong: bool,
    prominence: float,
    transition: str,
) -> dict[str, Any]:
    return {
        "frame": frame,
        "score": round(float(np.clip(score, 0.0, 1.0)), 4),
        "prominence": round(float(max(0.0, prominence)), 4),
        "is_strong": is_strong,
        "dist_to_target": abs(frame - target_frame),
        "transition": transition,
    }


def _detect_extreme_fades(
    descriptor_frames: list[int],
    descriptors: list[FrameDescriptor],
    target_frame: int,
    effective_threshold: float,
    peak_prominence: float,
    effective_fps: float,
) -> list[dict[str, Any]]:
    """Detect fade-to/from-black or white and place the cut at the extreme plateau."""
    lumas = np.asarray([item.luma for item in descriptors], dtype=np.float32)
    if len(lumas) < 4:
        return []

    look = max(3, int(round(min(1.25, len(lumas) / max(effective_fps, 1.0)) * effective_fps)))
    candidates: list[dict[str, Any]] = []
    for bright, mask in (
        (False, lumas <= 0.10),
        (True, lumas >= 0.92),
    ):
        start = 0
        while start < len(mask):
            if not mask[start]:
                start += 1
                continue
            end = start
            while end + 1 < len(mask) and mask[end + 1]:
                end += 1

            left = lumas[max(0, start - look):start]
            right = lumas[end + 1:min(len(lumas), end + look + 1)]
            extreme = float(np.max(lumas[start:end + 1]) if bright else np.min(lumas[start:end + 1]))
            side_values = []
            if len(left):
                side_values.append(float(np.min(left) if bright else np.max(left)))
            if len(right):
                side_values.append(float(np.min(right) if bright else np.max(right)))
            if side_values:
                contrast = max((extreme - value) if bright else (value - extreme) for value in side_values)
                required = max(0.16, peak_prominence)
                if contrast >= required:
                    center = (start + end) // 2
                    score = max(effective_threshold, min(0.92, 0.52 + contrast * 0.65))
                    candidates.append(
                        _candidate(
                            descriptor_frames[center],
                            score,
                            target_frame,
                            is_strong=score >= 0.75,
                            prominence=contrast,
                            transition="fade",
                        )
                    )
            start = end + 1
    return candidates


def _detect_dissolves(
    descriptor_frames: list[int],
    descriptors: list[FrameDescriptor],
    pair_scores: list[float],
    target_frame: int,
    effective_threshold: float,
    peak_prominence: float,
    effective_fps: float,
) -> list[dict[str, Any]]:
    """Detect sustained gradual changes whose endpoints differ but have no hard peak."""
    if len(descriptors) < 7:
        return []

    half_span = _dissolve_half_span(effective_fps)
    provisional: list[tuple[int, dict[str, Any]]] = []
    for center in range(half_span, len(descriptors) - half_span):
        left = center - half_span
        right = center + half_span
        local_scores = np.asarray(pair_scores[left:right], dtype=np.float32)
        if len(local_scores) < 4 or float(np.max(local_scores)) >= effective_threshold * 1.08:
            continue

        endpoint = compare_descriptors(descriptors[left], descriptors[right])
        color_shift = max(endpoint.hsv, endpoint.luma_hist)
        sustained = float(np.percentile(local_scores, 70))
        before = np.asarray(pair_scores[max(0, left - half_span):left], dtype=np.float32)
        after = np.asarray(pair_scores[right:min(len(pair_scores), right + half_span)], dtype=np.float32)
        baseline_values = []
        if len(before):
            baseline_values.append(float(np.percentile(before, 70)))
        if len(after):
            baseline_values.append(float(np.percentile(after, 70)))
        baseline = min(baseline_values, default=0.0)
        gradual_prominence = sustained - baseline
        active_frames = int(np.count_nonzero(local_scores >= max(0.035, sustained * 0.65)))
        endpoint_gate = max(0.55, effective_threshold * 1.35)
        if (
            endpoint.score >= endpoint_gate
            and color_shift >= 0.38
            and gradual_prominence >= max(0.08, peak_prominence)
            and sustained >= max(0.045, peak_prominence * 0.35)
            and active_frames >= max(3, half_span // 2)
        ):
            score = max(effective_threshold, min(0.82, endpoint.score * 0.90 + sustained * 0.35))
            provisional.append(
                (
                    center,
                    _candidate(
                        descriptor_frames[center],
                        score,
                        target_frame,
                        is_strong=False,
                        prominence=gradual_prominence,
                        transition="dissolve",
                    ),
                )
            )

    candidates: list[dict[str, Any]] = []
    run: list[tuple[int, dict[str, Any]]] = []
    for item in provisional:
        if run and item[0] - run[-1][0] > half_span:
            candidates.append(max(run, key=lambda value: value[1]["score"])[1])
            run = []
        run.append(item)
    if run:
        candidates.append(max(run, key=lambda value: value[1]["score"])[1])
    return candidates


def _dissolve_half_span(effective_fps: float) -> int:
    """Return the temporal half-window used by gradual-transition evidence."""
    return max(2, min(18, int(round(effective_fps * 0.30))))


def _merge_nearby_candidates(
    candidates: list[dict[str, Any]],
    effective_fps: float,
) -> list[dict[str, Any]]:
    """Keep a single strongest candidate for each physical transition."""
    radius = max(2, int(round(effective_fps * 0.55)))
    priority = {"fade": 2, "hard": 1, "dissolve": 0}
    kept: list[dict[str, Any]] = []
    for item in sorted(
        candidates,
        key=lambda value: (priority.get(value.get("transition", ""), -1), value["score"]),
        reverse=True,
    ):
        if all(abs(item["frame"] - existing["frame"]) > radius for existing in kept):
            kept.append(item)
    return sorted(kept, key=lambda item: item["frame"])


def scan_window_cuts(
    reader: FrameReader,
    window_start_frame: int,
    window_end_frame: int,
    target_frame: int,
    algorithm: str,
    sensitivity: float,
    cut_threshold: float,
    peak_prominence: float,
    effective_fps: float = 30.0,
    strong_cut_threshold: float = 0.75,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Scan frames in [window_start_frame, window_end_frame] to identify candidate scene cuts."""
    if window_end_frame < window_start_frame:
        return []

    requested_start = window_start_frame
    requested_end = window_end_frame
    # Dissolve prominence needs both the transition span and a baseline span.
    # Keeping both on each side avoids creating gradual candidates merely because
    # a legal segmentation window starts in the middle of ongoing motion.
    peak_context = max(5, 2 * _dissolve_half_span(effective_fps))
    analysis_start = max(1, requested_start - peak_context)
    analysis_end = requested_end + peak_context

    # Decode local context on both sides so boundary frames receive the same
    # prominence evidence as candidates in the middle of a window.
    prev_frame = reader.get_frame(analysis_start - 1)
    if prev_frame is None:
        return []

    frame_indices: list[int] = []
    scores: list[float] = []
    descriptor_frames = [analysis_start - 1]
    descriptors = [describe_frame(prev_frame)]

    for f_idx in range(analysis_start, analysis_end + 1):
        curr_frame = reader.get_frame(f_idx)
        if curr_frame is None:
            break
        current_descriptor = describe_frame(curr_frame)
        difference = compare_descriptors(descriptors[-1], current_descriptor)
        score = difference.score
        if should_check_optical_flow(algorithm, difference, cut_threshold):
            motion = compute_motion_explanation(prev_frame, curr_frame)
            score = apply_motion_suppression(score, algorithm, motion)
        frame_indices.append(f_idx)
        scores.append(score)
        descriptor_frames.append(f_idx)
        descriptors.append(current_descriptor)
        prev_frame = curr_frame
        if progress_callback and requested_start <= f_idx <= requested_end:
            progress_callback(f_idx, requested_end)

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
            candidates.append(
                _candidate(
                    f_idx,
                    score,
                    target_frame,
                    is_strong=is_strong,
                    prominence=prominence,
                    transition="hard",
                )
            )

    candidates.extend(
        _detect_extreme_fades(
            descriptor_frames,
            descriptors,
            target_frame,
            effective_thresh,
            peak_prominence,
            effective_fps,
        )
    )
    candidates.extend(
        _detect_dissolves(
            descriptor_frames,
            descriptors,
            scores,
            target_frame,
            effective_thresh,
            peak_prominence,
            effective_fps,
        )
    )
    eligible = [
        candidate
        for candidate in candidates
        if requested_start <= int(candidate["frame"]) <= requested_end
    ]
    return _merge_nearby_candidates(eligible, effective_fps)


def _candidate_target_key(
    candidate: dict[str, Any],
    target_frame: int,
) -> tuple[int, int, float, float, int]:
    """Rank by target distance; use confidence only to break equal distances."""
    frame = int(candidate["frame"])
    return (
        abs(frame - target_frame),
        0 if candidate.get("is_strong") else 1,
        -float(candidate.get("score", 0.0)),
        -float(candidate.get("prominence", 0.0)),
        frame,
    )


def _candidate_earliest_key(candidate: dict[str, Any]) -> tuple[int, int, float, float]:
    """Rank by first legal transition; use confidence only for same-frame ties."""
    return (
        int(candidate["frame"]),
        0 if candidate.get("is_strong") else 1,
        -float(candidate.get("score", 0.0)),
        -float(candidate.get("prominence", 0.0)),
    )


def _candidate_selection_key(
    candidate: dict[str, Any],
    target_frame: int,
    selection_policy: str,
) -> tuple:
    if selection_policy == "earliest":
        return _candidate_earliest_key(candidate)
    if selection_policy == "target":
        return _candidate_target_key(candidate, target_frame)
    raise ValueError("selection_policy must be target or earliest")


def select_best_cut(
    candidates: list[dict[str, Any]],
    target_frame: int,
    window_start: int,
    window_end: int,
    selection_policy: str = "target",
) -> tuple[int, float, str]:
    """Select a target-nearest or earliest accepted cut according to policy."""
    if not candidates:
        return target_frame, 0.0, "target_fallback"

    best_candidate = min(
        candidates,
        key=lambda item: _candidate_selection_key(item, target_frame, selection_policy),
    )
    cut_type = "strong_scene" if best_candidate.get("is_strong") else "scene"
    return best_candidate["frame"], best_candidate["score"], cut_type


def _reliable_lookahead_candidates(
    candidates: list[dict[str, Any]],
    peak_prominence: float,
) -> list[dict[str, Any]]:
    """Reject malformed or sub-prominence records from the preparatory-cut path."""
    supported = {"hard", "fade", "dissolve"}
    return [
        candidate
        for candidate in candidates
        if candidate.get("transition") in supported
        and float(candidate.get("score", 0.0)) > 0.0
        and float(candidate.get("prominence", 0.0)) >= peak_prominence
    ]


def _scene_cut_type(candidate: dict[str, Any]) -> str:
    return "strong_scene" if candidate.get("is_strong") else "scene"


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
    selection_policy: str = "target",
) -> list[dict[str, Any]]:
    """Execute scene-aware segmentation with target or earliest-cut selection."""
    if selection_policy not in {"target", "earliest"}:
        raise ValueError("selection_policy must be target or earliest")

    earliest_mode = selection_policy == "earliest"
    min_frames = max(1, int(round(min_duration * effective_fps)))
    target_frames = max(min_frames, int(round(target_duration * effective_fps)))
    requested_max_frames = int(round(max_duration * effective_fps))
    max_frames = max(min_frames if earliest_mode else target_frames, requested_max_frames)

    # Short video handling
    cannot_split_scene = earliest_mode and total_frames < 2 * min_frames
    target_mode_single = not earliest_mode and total_frames <= target_frames
    if total_frames <= min_frames or cannot_split_scene or target_mode_single:
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
    reserved_candidate: dict[str, Any] | None = None

    with FrameReader(video_path) as reader:
        current_start = 0

        while current_start < total_frames:
            rem_frames = total_frames - current_start

            def _step_cb(cur, tot):
                if progress_callback:
                    progress_callback("analyzing", cur, total_frames)

            # A lookahead transition is committed after its preparatory boundary.
            # This also preserves gradual transitions that need context before their center.
            if reserved_candidate is not None:
                cut_frame = int(reserved_candidate["frame"])
                frame_len = cut_frame - current_start
                if min_frames <= frame_len <= max_frames:
                    segments.append({
                        "start_frame": current_start,
                        "end_frame": cut_frame,
                        "frame_count": frame_len,
                        "start_time": round(current_start / effective_fps, 3),
                        "end_time": round(cut_frame / effective_fps, 3),
                        "duration": round(frame_len / effective_fps, 3),
                        "cut_score": reserved_candidate["score"],
                        "cut_type": _scene_cut_type(reserved_candidate),
                        "constraint_warning": False,
                    })
                    current_start = cut_frame
                    reserved_candidate = None
                    continue
                reserved_candidate = None

            # A final remainder may still contain a scene cut when both resulting
            # segments can satisfy the minimum duration.
            if rem_frames <= max_frames:
                if rem_frames >= 2 * min_frames:
                    tail_window_start = current_start + min_frames
                    tail_window_end = total_frames - min_frames
                    tail_target = (
                        tail_window_start
                        if earliest_mode
                        else min(current_start + target_frames, tail_window_end)
                    )
                    tail_candidates = scan_window_cuts(
                        reader=reader,
                        window_start_frame=tail_window_start,
                        window_end_frame=tail_window_end,
                        target_frame=tail_target,
                        algorithm=algorithm,
                        sensitivity=sensitivity,
                        cut_threshold=cut_threshold,
                        peak_prominence=peak_prominence,
                        effective_fps=effective_fps,
                        strong_cut_threshold=strong_cut_threshold,
                        progress_callback=_step_cb,
                    )
                    if tail_candidates:
                        cut_frame, cut_score, cut_type = select_best_cut(
                            tail_candidates,
                            tail_target,
                            tail_window_start,
                            tail_window_end,
                            selection_policy,
                        )
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
                            "constraint_warning": False,
                        })
                        window_candidates_history.append({
                            "start": current_start,
                            "candidates": tail_candidates,
                            "cut": cut_frame,
                        })
                        current_start = cut_frame
                        continue

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
            target_cut = w_end if earliest_mode else min(w_end, current_start + target_frames)

            candidates = scan_window_cuts(
                reader=reader,
                window_start_frame=w_start,
                window_end_frame=w_end,
                target_frame=target_cut,
                algorithm=algorithm,
                sensitivity=sensitivity,
                cut_threshold=cut_threshold,
                peak_prominence=peak_prominence,
                effective_fps=effective_fps,
                strong_cut_threshold=strong_cut_threshold,
                progress_callback=_step_cb,
            )
            cut_frame, cut_score, cut_type = select_best_cut(
                candidates,
                target_cut,
                w_start,
                w_end,
                selection_policy,
            )

            # Search the blind zone only when the legal window had no scene cut.
            should_look_ahead = cut_type == "target_fallback"
            lookahead_start = w_end + 1
            lookahead_end = min(total_frames - min_frames, w_end + min_frames)
            if should_look_ahead and lookahead_start <= lookahead_end:
                lookahead_candidates = scan_window_cuts(
                    reader=reader,
                    window_start_frame=lookahead_start,
                    window_end_frame=lookahead_end,
                    target_frame=target_cut,
                    algorithm=algorithm,
                    sensitivity=sensitivity,
                    cut_threshold=cut_threshold,
                    peak_prominence=peak_prominence,
                    effective_fps=effective_fps,
                    strong_cut_threshold=strong_cut_threshold,
                    progress_callback=_step_cb,
                )
                lookahead_candidates = _reliable_lookahead_candidates(
                    lookahead_candidates,
                    peak_prominence,
                )
                future_candidate = min(
                    lookahead_candidates,
                    key=lambda item: _candidate_selection_key(
                        item,
                        target_cut,
                        selection_policy,
                    ),
                    default=None,
                )
                if future_candidate is not None:
                    future_frame = int(future_candidate["frame"])
                    preparatory_cut = future_frame - min_frames
                    can_prepare = (
                        w_start <= preparatory_cut <= w_end
                        and total_frames - future_frame >= min_frames
                    )
                    if cut_type == "target_fallback" and can_prepare:
                        cut_frame = preparatory_cut
                        cut_score = 0.0
                        reserved_candidate = future_candidate

            # Check for tail conflict: if cut_frame leaves remaining frames < min_frames
            after_rem = total_frames - cut_frame
            constraint_warning = False

            if 0 < after_rem < min_frames:
                # Tail optimization: try to find an alternative cut in candidates that keeps after_rem >= min_frames
                valid_alt = None
                for alt in sorted(
                    candidates,
                    key=lambda item: _candidate_selection_key(
                        item,
                        target_cut,
                        selection_policy,
                    ),
                ):
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
