# IVASTBOT HRI ROS 2 Mapping

This document describes the planned ROS 2 integration boundary for the
IVASTBOT HRI layer. The current implementation is local-first: it runs on
Windows with Python and pytest, uses fake or mock adapters, and does not
require ROS 2, Ubuntu, Nav2, robot hardware, camera hardware, serial devices,
network services, or external services.

The future robot runtime will run in an Ubuntu/ROS 2 environment. That runtime
will translate the HRI contract dictionaries into real ROS 2 messages, topics,
services, or actions. The current contracts and mock adapters let the system be
tested before that runtime exists.

## Integration Boundary

The files under `ivastbot_hri/core/` contain deterministic HRI logic:

- action keys and expression keys
- action contracts and `ActionResult`
- action routing
- cooldown handling
- interaction decisions
- expression recognition and smoothing

Core logic must not import `rclpy`. Keeping `rclpy` out of core code lets the
same logic run in Windows tests, local demos, and future ROS 2 deployments. It
also keeps robot runtime failures from breaking unit tests for decision logic.

ROS 2-specific integration belongs under `ivastbot_hri/adapters/`. The current
boundary files are:

- `ivastbot_hri/adapters/ros2_contracts.py`: logical message contract builders
- `ivastbot_hri/adapters/mock_ros2_adapter.py`: in-memory ROS 2-style test adapter
- `ivastbot_hri/adapters/ros2_adapter.py`: skeleton for future real ROS 2 publishing

Only adapter files may depend on ROS 2. The current `ROS2Adapter` skeleton uses
lazy runtime setup so importing the adapter does not require `rclpy`.

## Contract Shape

Phase 10 introduced logical contract dictionaries with this common shape:

```python
{
    "channel": "hri.face.command",
    "command": "SHOW_HAPPY_FACE",
    "payload": {},
    "timestamp": None,
    "source": "ivastbot_hri",
    "correlation_id": None,
}
```

The logical channel names are not real ROS 2 topics yet. They are stable
contract categories that future ROS 2 code can map to topics, services, or
actions.

## Channel Mapping

| Logical channel | Purpose | Producer | Consumer | Command examples | Payload shape | Future ROS 2 mapping suggestion |
| --- | --- | --- | --- | --- | --- | --- |
| `hri.face.command` | Send face expression and gaze commands. | `ActionLibrary` through face adapters. | Face UI node or robot face display node. | `SHOW_HAPPY_FACE`, `SHOW_NEUTRAL_FACE`, `LOOK_LEFT`, `LOOK_RIGHT`, `LOOK_CENTER` | Empty dict or optional timing/debug fields such as `{"duration": 1.0}`. | Topic: `/ivastbot/hri/face_command` |
| `hri.gesture.command` | Send high-level gesture commands. | `ActionLibrary` through gesture adapters. | Gesture controller node or robot arm/body gesture node. | `WAVE_HAND`, `POINT_LEFT`, `POINT_RIGHT`, `POINT_FORWARD` | Empty dict or optional timing fields such as `{"duration": 1.0}`. | Topic: `/ivastbot/hri/gesture_command` |
| `hri.navigation.command` | Request high-level guidance behavior. | `ActionLibrary` through navigation adapters. | Navigation coordinator or future Nav2 bridge node. | `GUIDE_TO_TARGET` | Target payloads such as `{"target_id": "room_301"}` or `{"target": "lab"}`. | Action: `/ivastbot/hri/guide_to_target` |
| `hri.stop.command` | Stop or cancel current HRI-related action. | `ActionLibrary` through gesture or navigation adapters. | Gesture, navigation, or coordination node. | `STOP_ACTION` | Empty dict or context such as `{"reason": "operator"}`. | Topic or service: `/ivastbot/hri/stop` |
| `hri.status.event` | Report status and feedback from adapters or robot runtime. | Future ROS 2 adapter, robot runtime, or coordinator node. | Logs, UI, monitoring, or interaction manager feedback path. | `action_started`, `action_completed`, `action_failed`, `cooldown_skipped` | Event details such as `{"action_key": "WAVE_HAND", "reason": "executed"}`. | Topic: `/ivastbot/hri/status_event` |

## Local Development Role

Windows development covers:

- core HRI decision logic
- action validation and result formatting
- local demos
- fake face, gesture, and navigation adapters
- mock ROS 2-style adapters
- pytest coverage for contracts and adapter boundaries

This lets the HRI layer evolve without needing Ubuntu, ROS 2, Nav2, or robot
hardware for every change.

## Future ROS 2 Runtime Role

The future Ubuntu/ROS 2 runtime should provide real `rclpy` nodes and
publishers. It should translate the current contract dictionaries into chosen
ROS 2 message types and wire them to robot-specific consumers.

Likely future responsibilities include:

- mapping `hri.face.command` contracts to a face display topic
- mapping `hri.gesture.command` contracts to gesture controller commands
- mapping `hri.navigation.command` contracts to a guidance action or Nav2 bridge
- mapping `hri.stop.command` contracts to cancel or stop behavior
- publishing `hri.status.event` feedback for observability and coordination

## Future Integration Checklist

- Confirm the ROS 2 Humble environment.
- Create a real ROS 2 package or integrate into an existing robot package.
- Map contract dictionaries to ROS message types.
- Implement real publishers, subscribers, and action clients.
- Test the face command topic.
- Test the gesture command topic.
- Test the navigation goal action.
- Test stop and cancel behavior.
- Test status feedback events.
