import importlib
import sys

import pytest

from ivastbot_hri.core.target_lock import (
    TargetCandidate,
    TargetLockManager,
    compute_bbox_area,
    compute_bbox_center,
    compute_iou,
    distance_between_centers,
    normalize_candidate,
)


def candidate(
    candidate_id,
    bbox,
    confidence=0.9,
    expression="neutral",
):
    return {
        "candidate_id": candidate_id,
        "bbox": bbox,
        "confidence": confidence,
        "features": {"expression": expression},
        "raw_backend_index": int(candidate_id)
        if isinstance(candidate_id, int)
        else None,
    }


def manager(**overrides):
    options = {
        "min_confidence": 0.5,
        "min_area": 100.0,
        "max_center_distance": 40.0,
        "max_lost_frames": 2,
        "switch_stability_frames": 3,
        "frame_width": 200.0,
        "frame_height": 100.0,
    }
    options.update(overrides)
    return TargetLockManager(**options)


def test_bbox_geometry_helpers():
    assert compute_bbox_center((10, 20, 30, 40)) == (25.0, 40.0)
    assert compute_bbox_area((10, 20, 30, 40)) == 1200.0
    assert compute_iou((0, 0, 10, 10), (5, 0, 10, 10)) == pytest.approx(
        1.0 / 3.0
    )
    assert compute_iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0.0


def test_normalize_candidate_calculates_derived_fields():
    normalized = normalize_candidate(
        candidate(4, {"x": 10, "y": 20, "width": 30, "height": 40})
    )

    assert isinstance(normalized, TargetCandidate)
    assert normalized.center_x == 25.0
    assert normalized.center_y == 40.0
    assert normalized.area == 1200.0
    assert normalized.raw_backend_index == 4


def test_distance_between_candidate_centers():
    first = candidate(1, (0, 0, 20, 20))
    second = candidate(2, (30, 40, 20, 20))

    assert distance_between_centers(first, second) == 50.0


def test_initial_selection_prefers_centered_candidate():
    lock = manager()

    selected = lock.update(
        [
            candidate(1, (5, 30, 30, 30)),
            candidate(2, (85, 35, 30, 30)),
        ]
    )

    assert selected.candidate_id == 2
    assert lock.current().candidate_id == 2


def test_larger_face_wins_when_center_distance_is_equal():
    lock = manager()

    selected = lock.update(
        [
            candidate(1, (60, 35, 20, 30)),
            candidate(2, (110, 25, 40, 50)),
        ]
    )

    assert selected.candidate_id == 2


def test_low_confidence_and_small_candidates_are_filtered():
    lock = manager()

    assert lock.update(
        [
            candidate(1, (85, 35, 30, 30), confidence=0.2),
            candidate(2, (95, 45, 5, 5), confidence=0.9),
        ]
    ) is None
    assert not lock.is_locked()


def test_locked_target_remains_stable_across_nearby_movement():
    lock = manager()
    lock.update([candidate(1, (80, 30, 30, 30))])

    selected = lock.update(
        [
            candidate(1, (86, 32, 30, 30)),
            candidate(2, (95, 35, 30, 30)),
        ]
    )

    assert selected.candidate_id == 1
    assert lock.current().candidate_id == 1


def test_target_does_not_switch_immediately_to_better_candidate():
    lock = manager(switch_stability_frames=2)
    lock.update([candidate(1, (80, 30, 30, 30))])

    selected = lock.update(
        [
            candidate(1, (55, 30, 30, 30)),
            candidate(2, (85, 35, 30, 30)),
        ]
    )

    assert selected.candidate_id == 1


def test_target_switches_after_stability_threshold():
    lock = manager(switch_stability_frames=2)
    lock.update([candidate(1, (80, 30, 30, 30))])
    frames = [
        candidate(1, (55, 30, 30, 30)),
        candidate(2, (85, 35, 30, 30)),
    ]

    lock.update(frames)
    selected = lock.update(frames)

    assert selected.candidate_id == 2
    assert lock.current().candidate_id == 2


def test_target_lock_tolerates_temporary_missing_frames():
    lock = manager(max_lost_frames=2)
    lock.update([candidate(1, (80, 30, 30, 30))])

    assert lock.update([]) is None
    assert lock.is_locked()
    assert lock.lost_frames == 1
    assert lock.current().candidate_id == 1


def test_target_unlocks_after_loss_exceeds_maximum():
    lock = manager(max_lost_frames=2)
    lock.update([candidate(1, (80, 30, 30, 30))])

    lock.update([])
    lock.update([])
    lock.update([])

    assert not lock.is_locked()
    assert lock.current() is None
    assert lock.lost_frames == 0


def test_empty_candidates_without_existing_lock_returns_none():
    lock = manager()

    assert lock.update([]) is None
    assert lock.debug_info(target_visible=False) == {
        "target_mode": "auto",
        "target_locked": False,
        "target_visible": False,
        "target_id": None,
        "target_backend_index": None,
        "target_confidence": 0.0,
        "target_bbox": None,
        "lost_frames": 0,
    }


def test_manual_lock_selects_candidate_by_id():
    lock = manager()
    candidates = [
        candidate(1, (20, 30, 30, 30)),
        candidate(2, (85, 35, 30, 30)),
    ]
    lock.update(candidates)

    selected = lock.manual_lock(1)

    assert selected.candidate_id == 1
    assert lock.is_manual_lock_active()
    assert lock.get_locked_target().candidate_id == 1
    assert lock.debug_info()["target_mode"] == "manual"


def test_manual_lock_selects_candidate_by_backend_index():
    lock = manager()
    candidates = [
        {
            "candidate_id": "left",
            "raw_backend_index": 7,
            "bbox": (20, 30, 30, 30),
            "confidence": 0.9,
            "features": {},
        },
        {
            "candidate_id": "right",
            "raw_backend_index": 9,
            "bbox": (85, 35, 30, 30),
            "confidence": 0.9,
            "features": {},
        },
    ]
    lock.update(candidates)

    selected = lock.manual_lock(7)

    assert selected.candidate_id == "left"
    assert selected.raw_backend_index == 7


def test_manual_unlock_returns_to_automatic_selection():
    lock = manager()
    candidates = [
        candidate(1, (20, 30, 30, 30)),
        candidate(2, (85, 35, 30, 30)),
    ]
    lock.update(candidates)
    lock.manual_lock(1)

    lock.manual_unlock()
    selected = lock.update(candidates)

    assert not lock.is_manual_lock_active()
    assert selected.candidate_id == 2
    assert lock.debug_info()["target_mode"] == "auto"


def test_manual_lock_prevents_automatic_switching():
    lock = manager(switch_stability_frames=1)
    initial = [
        candidate(1, (80, 30, 30, 30)),
        candidate(2, (10, 30, 30, 30)),
    ]
    lock.update(initial)
    lock.manual_lock(2)

    selected = lock.update(
        [
            candidate(1, (85, 35, 30, 30)),
            candidate(2, (12, 30, 30, 30)),
        ]
    )

    assert selected.candidate_id == 2
    assert lock.get_locked_target().candidate_id == 2


def test_manual_lock_tracks_geometry_when_backend_indices_reorder():
    lock = manager()
    lock.update(
        [
            candidate(0, (80, 30, 30, 30)),
            candidate(1, (140, 30, 30, 30)),
        ]
    )
    lock.manual_lock(0)

    selected = lock.update(
        [
            candidate(0, (140, 30, 30, 30)),
            candidate(1, (82, 32, 30, 30)),
        ]
    )

    assert selected.candidate_id == 1
    assert selected.bbox == (82.0, 32.0, 30.0, 30.0)


def test_manual_lock_tolerates_temporary_target_loss():
    lock = manager(max_lost_frames=2)
    lock.update([candidate(1, (80, 30, 30, 30))])
    lock.manual_lock(1)

    assert lock.update([]) is None
    assert lock.is_manual_lock_active()
    assert lock.get_locked_target().candidate_id == 1
    assert lock.debug_info(target_visible=False)["target_mode"] == "manual"


def test_manual_lock_enters_lost_state_after_maximum():
    lock = manager(max_lost_frames=1)
    lock.update([candidate(1, (80, 30, 30, 30))])
    lock.manual_lock(1)

    lock.update([])
    lock.update([])
    debug_info = lock.debug_info(target_visible=False)

    assert lock.is_manual_lock_active()
    assert lock.get_locked_target().candidate_id == 1
    assert debug_info["target_mode"] == "manual-lost"
    assert debug_info["target_locked"] is False
    assert debug_info["target_id"] == 1


def test_manual_lost_target_can_be_reacquired():
    lock = manager(max_lost_frames=0)
    lock.update([candidate(1, (80, 30, 30, 30))])
    lock.manual_lock(1)
    lock.update([])

    selected = lock.update([candidate(1, (82, 32, 30, 30))])

    assert selected.candidate_id == 1
    assert lock.debug_info()["target_mode"] == "manual"
    assert lock.debug_info()["target_locked"] is True


def test_cycle_next_and_previous_use_backend_order():
    lock = manager()
    candidates = [
        candidate(5, (20, 30, 30, 30)),
        candidate(1, (85, 35, 30, 30)),
        candidate(3, (140, 30, 30, 30)),
    ]
    lock.update(candidates)

    first = lock.cycle_next_candidate(candidates)
    second = lock.cycle_next_candidate(candidates)
    previous = lock.cycle_previous_candidate(candidates)

    assert first.raw_backend_index == 3
    assert second.raw_backend_index == 5
    assert previous.raw_backend_index == 3


def test_cycle_with_empty_candidates_is_safe():
    lock = manager()

    assert lock.cycle_next_candidate([]) is None
    assert lock.cycle_previous_candidate([]) is None
    assert not lock.is_manual_lock_active()


def test_importing_target_lock_has_no_optional_runtime_dependencies():
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "numpy",
        "sklearn",
        "tensorflow",
        "torch",
        "openni",
        "requests",
        "rclpy",
        "serial",
        "websocket",
        "websockets",
    }
    before = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }

    sys.modules.pop("ivastbot_hri.core.target_lock", None)
    module = importlib.import_module("ivastbot_hri.core.target_lock")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.TargetLockManager is not None
    assert after == before
