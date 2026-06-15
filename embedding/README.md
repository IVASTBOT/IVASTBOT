# Hướng Dẫn Sử Dụng & Khởi Chạy iVASTBot Workspace

iVASTBot là robot tiếp tân chạy trên nền tảng **ROS 2 Humble**, kết hợp khả năng tự hành di động (SLAM + Nav2) cùng luồng hội thoại giọng nói tiếng Việt thời gian thực (STT → LLM → TTS).

---

## 🏗️ Kiến Trúc Hệ Thống (System Architecture)

### 1. Luồng di chuyển & Tự hành:
```
RPLidar A2M8 (/dev/ttyUSB0) ──> /scan_raw ──> scan_filter_node ──> /scan ──> SLAM / Nav2
Tay cầm Gamepad (hoặc Nav2 Goal) ──> /cmd_vel ──> ros2_control (IDS830HW) ──> Động cơ
```

### 2. Luồng hội thoại tiếng Việt:
```
ReSpeaker 4-Mic ──> Âm thanh ──> stt_worker (PhoWhisper) ──> /conversation/stt/final
  └──> session_node (Quản lý trạng thái & LED)
  └──> llm_worker (GPT-4o Streaming) ──> tts_worker (OpenAI TTS) ──> Loa (Phát âm thanh)
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Biên Dịch (Build Workspace)

Trước khi chạy, hãy kết nối đầy đủ thiết bị phần cứng (Lidar, Tay cầm, Driver động cơ CAN, Mic ReSpeaker) và thực hiện các bước sau:

```bash
# 1. Di chuyển vào thư mục workspace
cd /home/roscube/ivastbot_ws

# 2. Source môi trường ROS 2 mặc định
source /opt/ros/humble/setup.bash

# 3. Biên dịch toàn bộ workspace
colcon build --symlink-install

# 4. Source workspace đã biên dịch
source install/setup.bash
```

> [!TIP]
> Sử dụng `--symlink-install` giúp các chỉnh sửa file Python (`.py`) hoặc file Launch có hiệu lực ngay lập tức mà không cần biên dịch lại.

---

## 🚀 Hướng Dẫn Khởi Chạy Chi Tiết (Detailed Launch Guide)

### Bước 1: Khởi chạy phần cứng cơ sở (Robot Base)
Chạy driver động cơ điều khiển hai bánh, thiết lập tọa độ liên kết TF, cảm biến Lidar và **mặc định khởi chạy cả tay cầm gamepad**:
```bash
ros2 launch bringup bringup.launch.py lidar_serial_port:=/dev/ttyUSB0
```
*(Nếu muốn tắt tay cầm khi chạy bringup, thêm đối số `teleop:=false`)*

### Bước 2: Điều khiển Robot bằng Tay Cầm (Gamepad)
Node điều khiển tay cầm được bật **mặc định** ngay khi khởi chạy robot cơ sở (`bringup.launch.py`). Tốc độ khởi đầu mặc định là **0.1** cho cả tốc độ tịnh tiến (linear) và tốc độ xoay (angular) để đảm bảo an toàn khi bắt đầu lái.

#### 🎮 Cấu hình nút điều khiển tay cầm (Xbox / Logitech XInput):
* **Cần Analog Trái (Left Stick Y)**: Di chuyển Tiến / Lùi.
* **Cần Analog Phải (Right Stick X)**: Xoay Trái / Phải tại chỗ.
* **Nút Y / A**: Tăng / Giảm giới hạn tốc độ tịnh tiến tối đa (từng lượng `0.05` m/s).
* **Nút X / B**: Giảm / Tăng giới hạn tốc độ xoay tối đa (từng lượng `0.05` rad/s).
* **Phím L2 + R2 (Nhấn cùng lúc)**: Dừng khẩn cấp robot (E-Stop).
* **L1 / R1 (Bumpers) hoặc D-pad**: Di chuyển/Xoay với tốc độ định sẵn.

*Lưu ý: Các nút Y, A, X, B chỉ dùng để tăng/giảm tốc độ cài đặt giới hạn và không trực tiếp điều khiển robot chạy.*

#### Khởi chạy riêng lẻ gamepad (để test hoặc chạy độc lập):
```bash
ros2 launch gamepad gamepad_teleop.launch.py device:=/dev/input/js0
```

---

### Bước 3: Tạo Bản Đồ SLAM (Mapping)
Khởi chạy bộ lọc Lidar (`scan_filter`), thuật toán vẽ bản đồ (`slam_toolbox`) và node tay cầm gamepad điều khiển:
```bash
# Bật bộ quét và vẽ bản đồ kèm tay cầm
ros2 launch bringup slam_bringup.launch.py lidar_serial_port:=/dev/ttyUSB0 rviz:=true teleop:=true
```
Lái robot đi xung quanh bằng tay cầm để tạo bản đồ hoàn chỉnh trên màn hình RViz.

#### Lưu bản đồ sau khi quét xong:
```bash
ros2 run nav2_map_server map_saver_cli -f ~/ivastbot_map
```
Bản đồ sẽ lưu thành 2 file: `~/ivastbot_map.yaml` và `~/ivastbot_map.pgm`.

---

### Bước 4: Chạy Tự Hành Dẫn Đường (Navigation - Nav2)
Sau khi đã khởi chạy base hệ thống (`bringup.launch.py` ở Bước 1), khởi chạy hệ thống dẫn đường tự động tránh vật cản:
```bash
ros2 launch bringup nav_bringup.launch.py map:=/home/roscube/ivastbot_map.yaml rviz:=true
```
*Sử dụng công cụ **"2D Pose Estimate"** trên RViz để định vị ban đầu cho robot, sau đó dùng **"Nav2 Goal"** để chỉ định điểm đích robot tự đi tới.*

---

### Bước 4.5: Quản Lý Waypoint (Lưu / Liệt kê / Đi tới / Xóa)

Waypoint mặc định được lưu trong `src/navigation/maps/my_map_waypoints.yaml` và được dùng bởi cả `waypoint_goto`, `waypoint_saver`, và `guide_node` (phần dẫn đường bằng giọng nói). Sửa file `aliases` (`src/conversation_pipeline/config/waypoint_aliases.yaml`) khi thêm waypoint mới để robot nhận diện được tên gọi tiếng Việt.

> Yêu cầu: Nav2 (Bước 4) đang chạy và robot đã được định vị (AMCL có pose). `waypoint_saver` đọc `/amcl_pose`, `waypoint_goto` gọi action `/navigate_to_pose`.

#### Lưu vị trí hiện tại của robot thành waypoint:
```bash
# Robot đang đứng ở vị trí muốn lưu (đã set 2D Pose Estimate xong)
ros2 run navigation waypoint_saver -n diem_don_khach
ros2 run navigation waypoint_saver -n phong_robot
ros2 run navigation waypoint_saver -n phong_thay_tien
```

#### Liệt kê tất cả waypoint đã lưu:
```bash
ros2 run navigation waypoint_saver --list
# hoặc
ros2 run navigation waypoint_goto --list
```

#### Gửi robot đi đến một waypoint:
```bash
ros2 run navigation waypoint_goto -n diem_don_khach
ros2 run navigation waypoint_goto -n phong_robot
```

#### Xóa một waypoint:
```bash
ros2 run navigation waypoint_saver -d ten_waypoint_can_xoa
```

#### Dùng file YAML khác (không phải mặc định):
```bash
ros2 run navigation waypoint_saver -n phong_hop --file ~/my_other_waypoints.yaml
ros2 run navigation waypoint_goto -n phong_hop --file ~/my_other_waypoints.yaml
```

---

### Bước 5: Luồng Hội Thoại Giọng Nói Tiếng Việt
Mỗi node dưới đây cần chạy trên một Terminal riêng biệt (nhớ chạy `source install/setup.bash` trước mỗi lệnh):

#### 🔑 Thiết lập khóa API OpenAI trước:
```bash
export OPENAI_API_KEY="your-api-key-here"
export WS_ROOT=/home/roscube/ivastbot_ws
```

#### Khởi chạy các Node thành phần:
1. **Chạy Node Nhận Dạng Giọng Nói (STT):**
   ```bash
   ros2 run conversation_workers stt_worker
   ```
2. **Chạy Node Hỏi Đáp LLM (GPT-4o):**
   ```bash
   ros2 run conversation_workers llm_worker
   ```
3. **Chạy Node Chuyển Văn Bản Thành Giọng Nói (TTS):**
   ```bash
   ros2 run conversation_workers tts_worker
   ```
4. **Chạy Node Quản Lý Phiên Hội Thoại (Session Node):**
   ```bash
   ros2 run conversation_pipeline session_node
   ```

---

## 🔌 Danh Sách Phần Cứng & Cổng Kết Nối

| Thiết bị | Cổng mặc định (Port) | Gói điều khiển (Package) |
| :--- | :--- | :--- |
| **RPLidar A2M8** | `/dev/ttyUSB0` | `sllidar_ros2` |
| **Bộ chuyển đổi CAN (SLCAN)** | `/dev/ttyACM0` | `ids830_hw` |
| **Tay cầm Gamepad** | `/dev/input/js0` | `gamepad` |
| **Micro ReSpeaker 4-Mic** | Cổng USB | `respeaker_ros` |
