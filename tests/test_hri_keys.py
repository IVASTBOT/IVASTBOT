import importlib
import sys


EXPECTED_PERSON_KEYS = (
    "NO_PERSON",
    "PERSON_LEFT",
    "PERSON_CENTER",
    "PERSON_RIGHT",
)

EXPECTED_EXPRESSION_KEYS = (
    "EXPR_NEUTRAL",
    "EXPR_HAPPY",
    "EXPR_SURPRISE",
    "EXPR_CONFUSED",
    "EXPR_UNKNOWN",
)

EXPECTED_ACTION_KEYS = (
    "IDLE",
    "LOOK_LEFT",
    "LOOK_RIGHT",
    "LOOK_CENTER",
    "SHOW_NEUTRAL_FACE",
    "SHOW_HAPPY_FACE",
    "SHOW_THINKING_FACE",
    "SHOW_GUIDING_FACE",
    "WAVE_HAND",
    "POINT_LEFT",
    "POINT_RIGHT",
    "POINT_FORWARD",
    "GUIDE_TO_TARGET",
    "STOP_ACTION",
)

EXPECTED_ALL_KEYS = (
    EXPECTED_PERSON_KEYS + EXPECTED_EXPRESSION_KEYS + EXPECTED_ACTION_KEYS
)


def import_keys_module():
    return importlib.import_module("ivastbot_hri.core.keys")


def test_expected_keys_exist_and_values_match_names():
    keys = import_keys_module()

    for key_name in EXPECTED_ALL_KEYS:
        assert hasattr(keys, key_name)
        assert getattr(keys, key_name) == key_name


def test_grouped_collections_contain_expected_keys():
    keys = import_keys_module()

    assert keys.PERSON_KEYS == EXPECTED_PERSON_KEYS
    assert keys.EXPRESSION_KEYS == EXPECTED_EXPRESSION_KEYS
    assert keys.ACTION_KEYS == EXPECTED_ACTION_KEYS
    assert keys.ALL_KEYS == EXPECTED_ALL_KEYS


def test_keys_are_unique():
    keys = import_keys_module()

    assert len(keys.ALL_KEYS) == len(set(keys.ALL_KEYS))


def test_keys_import_has_no_ros_hardware_camera_or_network_dependency():
    forbidden_roots = {
        "cv2",
        "mediapipe",
        "openni",
        "requests",
        "rclpy",
        "websocket",
        "websockets",
    }
    before = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }

    sys.modules.pop("ivastbot_hri.core.keys", None)
    keys = import_keys_module()

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert keys.NO_PERSON == "NO_PERSON"
    assert after == before
