# IVASTBOT UART Gesture Adapter

Phase 19 adds a Linux-only UART implementation behind the existing HRI
`GestureAdapter` boundary. Windows development and automated tests continue to
use `FakeGestureAdapter` by default.

## Runtime flow

```text
ActionLibrary
  -> GestureAdapter.send("WAVE_HAND")
  -> LinuxUARTGestureAdapter.wave()
  -> RobotUARTClient.send_pose()
  -> librobot_uart.so:robot_send_raw()
  -> 12-byte UART packet at 115200 baud
```

The shared library is not loaded when Python imports the module or when the
factory creates an adapter. `ctypes.CDLL` runs only when
`LinuxUARTGestureAdapter.connect()` is called. A real connection is rejected
with a clear error on Windows.

## Backend configuration

The gesture factory reads these environment variables:

```text
HRI_GESTURE_BACKEND=fake
HRI_GESTURE_BACKEND=uart
HRI_GESTURE_PORT=/dev/ttyUSB0
HRI_GESTURE_LIBRARY=/path/to/librobot_uart.so
```

The default backend is `fake`. To inject the selected adapter:

```python
from ivastbot_hri.adapters.gesture_adapter_factory import create_gesture_adapter
from ivastbot_hri.core.action_library import ActionLibrary

gesture_adapter = create_gesture_adapter()
action_library = ActionLibrary(gesture_adapter=gesture_adapter)
```

The UART backend implements only verified physical behavior:

- `WAVE_HAND`
- the internal default/neutral pose used by `home()`, `neutral()`, and
  `STOP_ACTION`

Pointing and other physical gestures remain unsupported until robot poses are
verified.

## Windows verification

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
Remove-Item Env:HRI_GESTURE_BACKEND -ErrorAction SilentlyContinue
python -m pytest tests -q
git diff --check
```

No UART device, native library, ROS 2 installation, or robot is required.

## Build on the Linux robot

The checked-in native source is under `ivastbot_hri/native/robot_uart`. Do not
copy or reuse the reference x86-64 shared object; rebuild for the target
computer:

```bash
cd /path/to/IVASTBOT_HRI_WORK/ivastbot_hri/native/robot_uart
make -B
file librobot_uart.so
```

The build output is intentionally ignored by Git.

## Real-hardware verification

Keep the robot arm area clear and begin with the home-only command:

```bash
cd /path/to/IVASTBOT_HRI_WORK
python -m ivastbot_hri.demos.uart_gesture_demo \
  --port /dev/ttyUSB0 \
  --lib ivastbot_hri/native/robot_uart/librobot_uart.so \
  --action home \
  --speed 15
```

After visually confirming the neutral pose, run the operator-confirmed wave:

```bash
python -m ivastbot_hri.demos.uart_gesture_demo \
  --port /dev/ttyUSB0 \
  --lib ivastbot_hri/native/robot_uart/librobot_uart.so \
  --action wave \
  --speed 15
```

The demo moves to neutral, requires the operator to type `wave`, executes the
verified sequence, returns to neutral, and disconnects in a `finally` block.
The deployed user must have permission to access `/dev/ttyUSB0`.

Physical checks still required on the robot:

- native library architecture and dynamic loading
- serial device identity and permissions
- arm direction, speed, clearance, and emergency-stop readiness
- neutral and wave poses on the actual joint calibration
