"""Dependency-free face target selection and tracking helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable


BBox = tuple[float, float, float, float]


@dataclass
class TargetCandidate:
    """Normalized face candidate used by the target lock manager."""

    candidate_id: Any
    bbox: BBox
    center_x: float
    center_y: float
    area: float
    confidence: float
    features: dict = field(default_factory=dict)
    raw_backend_index: int | None = None
    frame_index: int | None = None


def compute_bbox_center(bbox) -> tuple[float, float]:
    """Return the center point for an ``(x, y, width, height)`` box."""
    x, y, width, height = _normalize_bbox(bbox)
    return x + width / 2.0, y + height / 2.0


def compute_bbox_area(bbox) -> float:
    """Return the non-negative area of a bounding box."""
    _, _, width, height = _normalize_bbox(bbox)
    return width * height


def compute_iou(bbox_a, bbox_b) -> float:
    """Return intersection-over-union for two bounding boxes."""
    ax, ay, aw, ah = _normalize_bbox(bbox_a)
    bx, by, bw, bh = _normalize_bbox(bbox_b)

    intersection_width = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    intersection_height = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    intersection = intersection_width * intersection_height
    union = aw * ah + bw * bh - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def distance_between_centers(candidate_a, candidate_b) -> float:
    """Return Euclidean center distance between two candidates."""
    first = normalize_candidate(candidate_a)
    second = normalize_candidate(candidate_b)
    return math.hypot(
        first.center_x - second.center_x,
        first.center_y - second.center_y,
    )


def normalize_candidate(candidate) -> TargetCandidate:
    """Normalize a candidate mapping or return a normalized candidate copy."""
    if isinstance(candidate, TargetCandidate):
        source = {
            "candidate_id": candidate.candidate_id,
            "bbox": candidate.bbox,
            "confidence": candidate.confidence,
            "features": candidate.features,
            "raw_backend_index": candidate.raw_backend_index,
            "frame_index": candidate.frame_index,
        }
    elif isinstance(candidate, dict):
        source = candidate
    else:
        raise TypeError("Target candidate must be a mapping or TargetCandidate")

    bbox = _normalize_bbox(source.get("bbox"))
    center_x, center_y = compute_bbox_center(bbox)
    confidence = _finite_number(source.get("confidence", 0.0), "confidence")
    confidence = min(1.0, max(0.0, confidence))
    features = source.get("features")
    if not isinstance(features, dict):
        features = {}

    raw_backend_index = source.get("raw_backend_index")
    if raw_backend_index is not None:
        raw_backend_index = _non_negative_int(
            raw_backend_index,
            "raw_backend_index",
        )

    candidate_id = source.get("candidate_id")
    if candidate_id is None:
        candidate_id = raw_backend_index

    frame_index = source.get("frame_index")
    if frame_index is not None:
        frame_index = _non_negative_int(frame_index, "frame_index")

    return TargetCandidate(
        candidate_id=candidate_id,
        bbox=bbox,
        center_x=center_x,
        center_y=center_y,
        area=compute_bbox_area(bbox),
        confidence=confidence,
        features=dict(features),
        raw_backend_index=raw_backend_index,
        frame_index=frame_index,
    )


class TargetLockManager:
    """Select one face candidate and keep it stable across frames."""

    def __init__(
        self,
        min_confidence: float = 0.5,
        min_area: float = 400.0,
        max_center_distance: float = 120.0,
        max_lost_frames: int = 3,
        switch_stability_frames: int = 3,
        prefer_center: bool = True,
        prefer_largest: bool = True,
        frame_width: float = 640.0,
        frame_height: float = 480.0,
    ):
        self.min_confidence = _unit_interval(
            min_confidence,
            "min_confidence",
        )
        self.min_area = _non_negative_number(min_area, "min_area")
        self.max_center_distance = _positive_number(
            max_center_distance,
            "max_center_distance",
        )
        self.max_lost_frames = _non_negative_int(
            max_lost_frames,
            "max_lost_frames",
        )
        self.switch_stability_frames = _positive_int(
            switch_stability_frames,
            "switch_stability_frames",
        )
        self.prefer_center = bool(prefer_center)
        self.prefer_largest = bool(prefer_largest)
        self.frame_width = _positive_number(frame_width, "frame_width")
        self.frame_height = _positive_number(frame_height, "frame_height")

        self._locked_target: TargetCandidate | None = None
        self._pending_switch: TargetCandidate | None = None
        self._pending_switch_frames = 0
        self.lost_frames = 0

    def update(
        self,
        candidates: Iterable[TargetCandidate | dict] | None,
    ) -> TargetCandidate | None:
        """Update the lock and return the visible locked candidate, if any."""
        valid_candidates = self._valid_candidates(candidates)

        if self._locked_target is None:
            selected = self._select_best(valid_candidates)
            if selected is not None:
                self._lock(selected)
            return selected

        matched = self._match_locked_target(valid_candidates)
        if matched is not None:
            self.lost_frames = 0
            challenger = self._select_best(
                candidate
                for candidate in valid_candidates
                if candidate is not matched
            )
            if (
                challenger is not None
                and self._selection_rank(challenger)
                < self._selection_rank(matched)
            ):
                if self._record_switch_candidate(challenger):
                    self._lock(challenger)
                    return challenger
            else:
                self._clear_pending_switch()

            self._locked_target = matched
            return matched

        self.lost_frames += 1
        challenger = self._select_best(valid_candidates)
        if challenger is not None and self._record_switch_candidate(challenger):
            self._lock(challenger)
            return challenger

        if self.lost_frames > self.max_lost_frames:
            self.reset()
        return None

    def current(self) -> TargetCandidate | None:
        """Return the retained lock, including during temporary target loss."""
        return self._locked_target

    def is_locked(self) -> bool:
        """Return whether a target lock is currently retained."""
        return self._locked_target is not None

    def reset(self) -> None:
        """Release the current target and all switch/loss state."""
        self._locked_target = None
        self._clear_pending_switch()
        self.lost_frames = 0

    def set_frame_size(self, width: float, height: float) -> None:
        """Update frame dimensions used by center preference."""
        self.frame_width = _positive_number(width, "frame_width")
        self.frame_height = _positive_number(height, "frame_height")

    def debug_info(self, target_visible: bool = True) -> dict:
        """Return JSON-like target state for overlays and local debugging."""
        target = self._locked_target
        return {
            "target_locked": target is not None,
            "target_visible": bool(target is not None and target_visible),
            "target_id": target.candidate_id if target is not None else None,
            "target_backend_index": (
                target.raw_backend_index if target is not None else None
            ),
            "target_confidence": (
                target.confidence if target is not None else 0.0
            ),
            "target_bbox": target.bbox if target is not None else None,
            "lost_frames": self.lost_frames,
        }

    def _valid_candidates(
        self,
        candidates: Iterable[TargetCandidate | dict] | None,
    ) -> list[TargetCandidate]:
        normalized = []
        for candidate in candidates or ():
            try:
                item = normalize_candidate(candidate)
            except (TypeError, ValueError):
                continue
            if (
                item.confidence >= self.min_confidence
                and item.area >= self.min_area
            ):
                normalized.append(item)
        return normalized

    def _select_best(
        self,
        candidates: Iterable[TargetCandidate],
    ) -> TargetCandidate | None:
        items = list(candidates)
        if not items:
            return None
        return min(items, key=self._selection_rank)

    def _selection_rank(self, candidate: TargetCandidate) -> tuple:
        center_distance = 0.0
        if self.prefer_center:
            center_distance = math.hypot(
                candidate.center_x - self.frame_width / 2.0,
                candidate.center_y - self.frame_height / 2.0,
            )
        area_rank = -candidate.area if self.prefer_largest else 0.0
        return (
            center_distance,
            area_rank,
            -candidate.confidence,
            str(candidate.candidate_id),
        )

    def _match_locked_target(
        self,
        candidates: list[TargetCandidate],
    ) -> TargetCandidate | None:
        matches = []
        for candidate in candidates:
            distance = distance_between_centers(
                self._locked_target,
                candidate,
            )
            iou = compute_iou(self._locked_target.bbox, candidate.bbox)
            if distance <= self.max_center_distance or iou > 0.0:
                same_id = (
                    self._locked_target.candidate_id is not None
                    and candidate.candidate_id
                    == self._locked_target.candidate_id
                )
                matches.append((not same_id, -iou, distance, candidate))

        if not matches:
            return None
        return min(matches, key=lambda item: item[:3])[3]

    def _record_switch_candidate(self, candidate: TargetCandidate) -> bool:
        if (
            self._pending_switch is not None
            and self._same_track(self._pending_switch, candidate)
        ):
            self._pending_switch_frames += 1
        else:
            self._pending_switch = candidate
            self._pending_switch_frames = 1

        self._pending_switch = candidate
        return self._pending_switch_frames >= self.switch_stability_frames

    def _same_track(
        self,
        first: TargetCandidate,
        second: TargetCandidate,
    ) -> bool:
        if (
            first.candidate_id is not None
            and first.candidate_id == second.candidate_id
        ):
            return True
        return (
            distance_between_centers(first, second)
            <= self.max_center_distance
        )

    def _lock(self, candidate: TargetCandidate) -> None:
        self._locked_target = candidate
        self.lost_frames = 0
        self._clear_pending_switch()

    def _clear_pending_switch(self) -> None:
        self._pending_switch = None
        self._pending_switch_frames = 0


def _normalize_bbox(bbox) -> BBox:
    if isinstance(bbox, dict):
        values = (
            bbox.get("x"),
            bbox.get("y"),
            bbox.get("width"),
            bbox.get("height"),
        )
    elif isinstance(bbox, (tuple, list)) and len(bbox) == 4:
        values = bbox
    else:
        raise ValueError("bbox must contain x, y, width, and height")

    x = _finite_number(values[0], "bbox x")
    y = _finite_number(values[1], "bbox y")
    width = _non_negative_number(values[2], "bbox width")
    height = _non_negative_number(values[3], "bbox height")
    return x, y, width, height


def _finite_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _non_negative_number(value, name: str) -> float:
    number = _finite_number(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return number


def _positive_number(value, name: str) -> float:
    number = _finite_number(value, name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


def _unit_interval(value, name: str) -> float:
    number = _finite_number(value, name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")
    return number


def _non_negative_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


__all__ = (
    "TargetCandidate",
    "TargetLockManager",
    "compute_bbox_area",
    "compute_bbox_center",
    "compute_iou",
    "distance_between_centers",
    "normalize_candidate",
)
