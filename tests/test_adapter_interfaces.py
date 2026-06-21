import importlib
import sys

from ivastbot_hri.adapters.face_bridge_adapter import FaceBridgeAdapter
from ivastbot_hri.adapters.fake_face_adapter import FakeFaceAdapter
from ivastbot_hri.adapters.fake_gesture_adapter import FakeGestureAdapter
from ivastbot_hri.adapters.fake_navigation_adapter import FakeNavigationAdapter
from ivastbot_hri.adapters.interfaces import (
    FaceAdapter,
    GestureAdapter,
    NavigationAdapter,
)
from ivastbot_hri.core import keys
from ivastbot_hri.core.action_library import ActionLibrary


def test_fake_face_adapter_conforms_to_face_adapter_interface():
    adapter = FakeFaceAdapter()

    assert isinstance(adapter, FaceAdapter)
    adapter.send(keys.SHOW_NEUTRAL_FACE)

    assert adapter.commands == [(keys.SHOW_NEUTRAL_FACE, {})]


def test_fake_gesture_adapter_conforms_to_gesture_adapter_interface():
    adapter = FakeGestureAdapter()

    assert isinstance(adapter, GestureAdapter)
    adapter.send(keys.WAVE_HAND)

    assert adapter.commands == [(keys.WAVE_HAND, {})]


def test_fake_navigation_adapter_conforms_to_navigation_adapter_interface():
    adapter = FakeNavigationAdapter()

    assert isinstance(adapter, NavigationAdapter)
    adapter.send(keys.GUIDE_TO_TARGET, {"target": "front_desk"})

    assert adapter.commands == [(keys.GUIDE_TO_TARGET, {"target": "front_desk"})]


def test_face_bridge_adapter_conforms_to_face_adapter_interface():
    adapter = FaceBridgeAdapter()

    assert isinstance(adapter, FaceAdapter)
    assert adapter.send(keys.SHOW_HAPPY_FACE) == {"emotion": "happy"}


def test_action_library_can_still_use_interface_conforming_adapters():
    face = FaceBridgeAdapter()
    gesture = FakeGestureAdapter()
    navigation = FakeNavigationAdapter()
    library = ActionLibrary(
        face_adapter=face,
        gesture_adapter=gesture,
        navigation_adapter=navigation,
    )

    happy_result = library.execute(keys.SHOW_HAPPY_FACE, {"duration": 1.0})
    wave_result = library.execute(keys.WAVE_HAND)
    guide_result = library.execute(keys.GUIDE_TO_TARGET, {"target_id": "desk"})

    assert happy_result.executed is True
    assert wave_result.executed is True
    assert guide_result.executed is True
    assert face.sent_commands == [{"duration": 1.0, "emotion": "happy"}]
    assert gesture.commands == [(keys.WAVE_HAND, {})]
    assert navigation.commands == [(keys.GUIDE_TO_TARGET, {"target_id": "desk"})]


def test_adapter_interfaces_import_has_no_ros_or_hardware_dependency():
    forbidden_roots = {
        "cv2",
        "mediapipe",
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

    sys.modules.pop("ivastbot_hri.adapters.interfaces", None)
    module = importlib.import_module("ivastbot_hri.adapters.interfaces")

    after = {
        name
        for name in sys.modules
        if name.split(".", maxsplit=1)[0] in forbidden_roots
    }
    assert module.FaceAdapter is not None
    assert module.GestureAdapter is not None
    assert module.NavigationAdapter is not None
    assert after == before
