#include "kinco_canopen_hw/kinco_hw.hpp"

#include <cstring>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <algorithm>

// Linux serial
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <sys/select.h>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "rclcpp/rclcpp.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace kinco_canopen_hw
{

static const auto LOG = "KincoCANopenHW";
namespace
{
double low_pass_alpha(double cutoff_hz, double dt)
{
  if (dt <= 0.0 || cutoff_hz <= 0.0) {
    return 1.0;
  }
  const double tau = 1.0 / (2.0 * M_PI * cutoff_hz);
  return dt / (tau + dt);
}
}  // namespace

// ============================================================
// Serial helpers
// ============================================================

bool KincoCANopenHW::serial_open(const std::string & port, int baudrate)
{
  serial_fd_ = ::open(port.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (serial_fd_ < 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOG),
      "Cannot open serial port '%s': %s", port.c_str(), strerror(errno));
    return false;
  }

  struct termios tty;
  std::memset(&tty, 0, sizeof(tty));
  if (tcgetattr(serial_fd_, &tty) != 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOG), "tcgetattr failed: %s", strerror(errno));
    ::close(serial_fd_);
    serial_fd_ = -1;
    return false;
  }

  // Map baudrate
  speed_t speed;
  switch (baudrate) {
    case 9600:   speed = B9600;   break;
    case 19200:  speed = B19200;  break;
    case 38400:  speed = B38400;  break;
    case 57600:  speed = B57600;  break;
    case 115200: speed = B115200; break;
    case 230400: speed = B230400; break;
    case 460800: speed = B460800; break;
    case 921600: speed = B921600; break;
    default:     speed = B115200; break;
  }

  cfsetispeed(&tty, speed);
  cfsetospeed(&tty, speed);

  // 8N1, no flow control
  tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
  tty.c_cflag &= ~(PARENB | PARODD | CSTOPB | CRTSCTS);
  tty.c_cflag |= CLOCAL | CREAD;

  // Raw mode
  tty.c_iflag &= ~(IXON | IXOFF | IXANY | IGNBRK | BRKINT | PARMRK |
                    ISTRIP | INLCR | IGNCR | ICRNL);
  tty.c_oflag &= ~OPOST;
  tty.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);

  tty.c_cc[VMIN]  = 0;
  tty.c_cc[VTIME] = 1;  // 100ms timeout

  if (tcsetattr(serial_fd_, TCSANOW, &tty) != 0) {
    RCLCPP_ERROR(rclcpp::get_logger(LOG), "tcsetattr failed: %s", strerror(errno));
    ::close(serial_fd_);
    serial_fd_ = -1;
    return false;
  }

  // Flush buffers
  tcflush(serial_fd_, TCIOFLUSH);

  RCLCPP_INFO(rclcpp::get_logger(LOG),
    "Serial port %s opened at %d baud", port.c_str(), baudrate);
  return true;
}

void KincoCANopenHW::serial_close()
{
  if (serial_fd_ >= 0) {
    ::close(serial_fd_);
    serial_fd_ = -1;
  }
}

void KincoCANopenHW::serial_write_str(const std::string & s)
{
  if (serial_fd_ < 0) return;
  ::write(serial_fd_, s.c_str(), s.size());
}

std::string KincoCANopenHW::serial_read_line(int timeout_ms)
{
  if (serial_fd_ < 0) return "";

  std::string line;
  auto deadline = std::chrono::steady_clock::now() +
                  std::chrono::milliseconds(timeout_ms);

  while (std::chrono::steady_clock::now() < deadline) {
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(serial_fd_, &fds);
    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 5000;  // 5ms poll

    if (select(serial_fd_ + 1, &fds, nullptr, nullptr, &tv) > 0) {
      char c;
      if (::read(serial_fd_, &c, 1) == 1) {
        if (c == '\r' || c == '\n') {
          if (!line.empty()) return line;
        } else {
          line += c;
        }
      }
    }
  }
  return line;
}

// ============================================================
// SLCAN protocol
// ============================================================

void KincoCANopenHW::slcan_open(int can_speed_code)
{
  // Close any existing session
  serial_write_str("C\r");
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  // Flush
  tcflush(serial_fd_, TCIOFLUSH);

  // Set CAN speed: S0=10k, S1=20k, S2=50k, S3=100k, S4=125k, S5=250k, S6=500k, S7=800k, S8=1M
  char cmd[4];
  std::snprintf(cmd, sizeof(cmd), "S%d\r", can_speed_code);
  serial_write_str(cmd);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  // Open CAN channel
  serial_write_str("O\r");
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  RCLCPP_INFO(rclcpp::get_logger(LOG), "SLCAN channel opened (speed code S%d)", can_speed_code);
}

void KincoCANopenHW::slcan_close()
{
  serial_write_str("C\r");
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
}

void KincoCANopenHW::slcan_send(uint32_t id, const uint8_t* data, uint8_t len)
{
  serial_write_str(slcan_format(id, data, len));
}

std::string KincoCANopenHW::slcan_format(uint32_t id, const uint8_t* data, uint8_t len)
{
  // SLCAN format: tIIILDD..DD\r
  char buf[32];
  int pos = std::snprintf(buf, sizeof(buf), "t%03X%d", id & 0x7FF, len);
  for (int i = 0; i < len; ++i) {
    pos += std::snprintf(buf + pos, sizeof(buf) - pos, "%02X", data[i]);
  }
  buf[pos++] = '\r';
  return std::string(buf, pos);
}

void KincoCANopenHW::slcan_send_batch(const std::string & combined)
{
  // Send all frames in ONE serial write — minimal inter-frame delay
  serial_write_str(combined);
}

bool KincoCANopenHW::slcan_recv(uint32_t & id, uint8_t* data, uint8_t & len, int timeout_ms)
{
  std::string line = serial_read_line(timeout_ms);
  if (line.empty() || line[0] != 't') return false;
  if (line.size() < 5) return false;

  // Parse: tIIILDD..DD
  char id_str[4] = {line[1], line[2], line[3], '\0'};
  id = static_cast<uint32_t>(std::strtoul(id_str, nullptr, 16));
  len = static_cast<uint8_t>(line[4] - '0');

  if (len > 8) return false;
  if (line.size() < 5 + len * 2) return false;

  for (int i = 0; i < len; ++i) {
    char byte_str[3] = {line[5 + i*2], line[6 + i*2], '\0'};
    data[i] = static_cast<uint8_t>(std::strtoul(byte_str, nullptr, 16));
  }
  return true;
}

// ============================================================
// RX background thread
// ============================================================

void KincoCANopenHW::rx_loop()
{
  while (rx_running_) {
    uint32_t id;
    uint8_t data[8];
    uint8_t len;

    if (slcan_recv(id, data, len, 20)) {
      std::lock_guard<std::mutex> lock(rx_mutex_);
      rx_responses_[id] = std::vector<uint8_t>(data, data + len);
      rx_response_stamps_[id] = std::chrono::steady_clock::now();
    }
  }
}

// ============================================================
// Lifecycle
// ============================================================

hardware_interface::CallbackReturn KincoCANopenHW::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) !=
      hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  auto get = [&](const std::string & key, const std::string & def) -> std::string {
    auto it = info.hardware_parameters.find(key);
    return (it != info.hardware_parameters.end()) ? it->second : def;
  };

  can_channel_      = get("can_channel",      "/dev/ttyACM0");
  serial_baud_      = std::stoi(get("serial_baudrate", "115200"));
  left_id_          = static_cast<uint8_t>(std::stoi(get("left_motor_id",  "1")));
  right_id_         = static_cast<uint8_t>(std::stoi(get("right_motor_id", "2")));
  gear_ratio_       = std::stoi(get("gear_ratio",       "9"));
  velocity_factor_  = std::stoi(get("velocity_factor",  "2731"));
  accel_raw_        = std::stoi(get("accel_raw",        "5000"));
  decel_raw_        = std::stoi(get("decel_raw",        "5000"));
  use_sync_         = (get("use_sync", "true") == "true");
  cmd_filter_cutoff_hz_ = std::stod(get("cmd_filter_cutoff_hz", "6.0"));
  feedback_filter_cutoff_hz_ = std::stod(get("feedback_filter_cutoff_hz", "12.0"));
  odom_filter_cutoff_hz_ = std::stod(get("odom_filter_cutoff_hz", "20.0"));
  max_cmd_delta_rad_s2_ = std::stod(get("max_cmd_delta_rad_s2", "8.0"));
  zero_hyst_enter_rad_s_ = std::stod(get("zero_hyst_enter_rad_s", "0.02"));
  zero_hyst_exit_rad_s_ = std::stod(get("zero_hyst_exit_rad_s", "0.04"));
  tpdo_timeout_ms_ = std::stoi(get("tpdo_timeout_ms", "120"));
  wheel_track_m_ = std::stod(get("wheel_track_m", "0.39"));
  if (wheel_track_m_ <= 1e-6) {
    wheel_track_m_ = 0.39;
  }

  if (info.joints.size() != 2) {
    RCLCPP_ERROR(rclcpp::get_logger(LOG),
      "Expected 2 joints, got %zu", info.joints.size());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(rclcpp::get_logger(LOG),
    "Init OK: serial=%s baud=%d left=%d right=%d gear=%d cmd_fc=%.2f fb_fc=%.2f odom_fc=%.2f tpdo_to=%dms",
    can_channel_.c_str(), serial_baud_, left_id_, right_id_, gear_ratio_,
    cmd_filter_cutoff_hz_, feedback_filter_cutoff_hz_, odom_filter_cutoff_hz_, tpdo_timeout_ms_);

  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn KincoCANopenHW::on_configure(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(rclcpp::get_logger(LOG), "Configuring serial SLCAN...");

  // Open serial port
  if (!serial_open(can_channel_, serial_baud_)) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // Open SLCAN channel (S6 = 500kbps CAN)
  slcan_open(6);

  // Start RX thread
  rx_running_ = true;
  rx_thread_ = std::thread(&KincoCANopenHW::rx_loop, this);

  // NMT: both motors Operational
  nmt_command(left_id_, 0x01);
  nmt_command(right_id_, 0x01);
  std::this_thread::sleep_for(std::chrono::milliseconds(500));

  // DS402 startup
  motor_startup(left_id_);
  motor_startup(right_id_);

  // Profile Velocity Mode
  motor_set_velocity_mode(left_id_, accel_raw_, decel_raw_);
  motor_set_velocity_mode(right_id_, accel_raw_, decel_raw_);

  // Map RPDO1 (receive velocity commands)
  motor_map_rpdo1(left_id_);
  motor_map_rpdo1(right_id_);

  // Map TPDO1 (motor auto-sends actual velocity on SYNC)
  motor_map_tpdo1(left_id_);
  motor_map_tpdo1(right_id_);

  RCLCPP_INFO(rclcpp::get_logger(LOG), "Both motors configured OK");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn KincoCANopenHW::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(rclcpp::get_logger(LOG), "Activating — motors enabled");
  hw_commands_[0] = 0.0;
  hw_commands_[1] = 0.0;
  filtered_hw_commands_[0] = 0.0;
  filtered_hw_commands_[1] = 0.0;
  limited_hw_commands_[0] = 0.0;
  limited_hw_commands_[1] = 0.0;
  filtered_hw_velocities_[0] = 0.0;
  filtered_hw_velocities_[1] = 0.0;
  raw_hw_velocities_[0] = 0.0;
  raw_hw_velocities_[1] = 0.0;
  control_hw_velocities_[0] = 0.0;
  control_hw_velocities_[1] = 0.0;
  odom_hw_velocities_[0] = 0.0;
  odom_hw_velocities_[1] = 0.0;
  zero_latched_[0] = true;
  zero_latched_[1] = true;
  command_filter_initialized_ = false;
  feedback_filter_initialized_ = false;
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn KincoCANopenHW::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(rclcpp::get_logger(LOG), "Deactivating — stopping motors");
  motor_send_velocity_pdo(left_id_, 0);
  motor_send_velocity_pdo(right_id_, 0);
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn KincoCANopenHW::on_cleanup(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(rclcpp::get_logger(LOG), "Cleaning up");
  rx_running_ = false;
  if (rx_thread_.joinable()) rx_thread_.join();
  slcan_close();
  serial_close();
  return hardware_interface::CallbackReturn::SUCCESS;
}

// ============================================================
// State / Command Interfaces
// ============================================================

std::vector<hardware_interface::StateInterface>
KincoCANopenHW::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> si;
  for (size_t i = 0; i < 2; ++i) {
    si.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_positions_[i]);
    si.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_VELOCITY, &hw_velocities_[i]);
  }
  return si;
}

std::vector<hardware_interface::CommandInterface>
KincoCANopenHW::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> ci;
  for (size_t i = 0; i < 2; ++i) {
    ci.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_VELOCITY, &hw_commands_[i]);
  }
  return ci;
}

// ============================================================
// Read / Write
// ============================================================

hardware_interface::return_type KincoCANopenHW::read(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & period)
{
  // TPDO1 is async (event-timer): motors continuously send velocity
  // RX thread updates rx_responses_ in background — just read the latest

  uint32_t tpdo1_left  = TPDO1_BASE + left_id_;
  uint32_t tpdo1_right = TPDO1_BASE + right_id_;

  int32_t raw_left = 0, raw_right = 0;
  bool left_fresh = false;
  bool right_fresh = false;
  const auto now = std::chrono::steady_clock::now();

  {
    std::lock_guard<std::mutex> lock(rx_mutex_);

    auto it_l = rx_responses_.find(tpdo1_left);
    auto ts_l = rx_response_stamps_.find(tpdo1_left);
    if (it_l != rx_responses_.end() && ts_l != rx_response_stamps_.end() && it_l->second.size() >= 4) {
      const auto age_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - ts_l->second).count();
      left_fresh = (age_ms <= tpdo_timeout_ms_);
    }
    if (left_fresh) {
      std::memcpy(&raw_left, it_l->second.data(), 4);
    }

    auto it_r = rx_responses_.find(tpdo1_right);
    auto ts_r = rx_response_stamps_.find(tpdo1_right);
    if (it_r != rx_responses_.end() && ts_r != rx_response_stamps_.end() && it_r->second.size() >= 4) {
      const auto age_ms = std::chrono::duration_cast<std::chrono::milliseconds>(now - ts_r->second).count();
      right_fresh = (age_ms <= tpdo_timeout_ms_);
    }
    if (right_fresh) {
      std::memcpy(&raw_right, it_r->second.data(), 4);
    }
  }

  raw_hw_velocities_[0] = left_fresh ? internal_to_wheel_rads(raw_left) : 0.0;
  raw_hw_velocities_[1] = right_fresh ? -internal_to_wheel_rads(raw_right) : 0.0;
  if (!left_fresh || !right_fresh) {
    static int stale_warn_count = 0;
    if (++stale_warn_count >= 50) {
      stale_warn_count = 0;
      RCLCPP_WARN(
        rclcpp::get_logger(LOG),
        "TPDO stale timeout (L fresh=%d R fresh=%d, timeout=%dms) -> fallback zero velocity",
        left_fresh ? 1 : 0, right_fresh ? 1 : 0, tpdo_timeout_ms_);
    }
  }

  const double dt = std::max(period.seconds(), 1e-4);
  const double fb_alpha = low_pass_alpha(feedback_filter_cutoff_hz_, dt);
  const double odom_alpha = low_pass_alpha(odom_filter_cutoff_hz_, dt);

  if (!feedback_filter_initialized_) {
    control_hw_velocities_[0] = raw_hw_velocities_[0];
    control_hw_velocities_[1] = raw_hw_velocities_[1];
    odom_hw_velocities_[0] = raw_hw_velocities_[0];
    odom_hw_velocities_[1] = raw_hw_velocities_[1];
    feedback_filter_initialized_ = true;
  } else {
    control_hw_velocities_[0] += fb_alpha * (raw_hw_velocities_[0] - control_hw_velocities_[0]);
    control_hw_velocities_[1] += fb_alpha * (raw_hw_velocities_[1] - control_hw_velocities_[1]);
    odom_hw_velocities_[0] += odom_alpha * (raw_hw_velocities_[0] - odom_hw_velocities_[0]);
    odom_hw_velocities_[1] += odom_alpha * (raw_hw_velocities_[1] - odom_hw_velocities_[1]);
  }

  // Export odom-friendly velocity to ros2_control interfaces
  hw_velocities_[0] = odom_hw_velocities_[0];
  hw_velocities_[1] = odom_hw_velocities_[1];

  // Debug: log velocities at 1Hz (every 100 cycles at 100Hz)
  static int dbg_count = 0;
  if (++dbg_count >= 100) {
    dbg_count = 0;
    if (std::abs(hw_velocities_[0]) > 0.01 || std::abs(hw_velocities_[1]) > 0.01) {
      RCLCPP_INFO(rclcpp::get_logger(LOG),
        "VEL raw(L=%d R=%d) fresh(L=%d R=%d) | odom L=%.3f R=%.3f | ctrl L=%.3f R=%.3f | omega=%.3f",
        raw_left, raw_right,
        left_fresh ? 1 : 0, right_fresh ? 1 : 0,
        hw_velocities_[0], hw_velocities_[1],
        control_hw_velocities_[0], control_hw_velocities_[1],
        (hw_velocities_[1] - hw_velocities_[0]) / wheel_track_m_);
    }
  }

  // Integrate position
  hw_positions_[0] += hw_velocities_[0] * dt;
  hw_positions_[1] += hw_velocities_[1] * dt;

  return hardware_interface::return_type::OK;
}

hardware_interface::return_type KincoCANopenHW::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & period)
{
  const double dt = std::max(period.seconds(), 1e-4);
  const double cmd_alpha = low_pass_alpha(cmd_filter_cutoff_hz_, dt);
  const double max_delta = max_cmd_delta_rad_s2_ * dt;

  if (!command_filter_initialized_) {
    filtered_hw_commands_[0] = hw_commands_[0];
    filtered_hw_commands_[1] = hw_commands_[1];
    limited_hw_commands_[0] = hw_commands_[0];
    limited_hw_commands_[1] = hw_commands_[1];
    command_filter_initialized_ = true;
  }

  for (size_t i = 0; i < 2; ++i) {
    filtered_hw_commands_[i] += cmd_alpha * (hw_commands_[i] - filtered_hw_commands_[i]);
    const double delta = std::clamp(
      filtered_hw_commands_[i] - limited_hw_commands_[i], -max_delta, max_delta);
    limited_hw_commands_[i] += delta;

    const double abs_limited = std::abs(limited_hw_commands_[i]);
    if (zero_latched_[i]) {
      if (abs_limited > zero_hyst_exit_rad_s_) {
        zero_latched_[i] = false;
      } else {
        limited_hw_commands_[i] = 0.0;
      }
    } else if (abs_limited < zero_hyst_enter_rad_s_) {
      zero_latched_[i] = true;
      limited_hw_commands_[i] = 0.0;
    }
  }

  int32_t cmd_left  = wheel_rads_to_internal(limited_hw_commands_[0]);
  int32_t cmd_right = -wheel_rads_to_internal(limited_hw_commands_[1]);

  // ---- Small deadband near zero only ----
  constexpr int32_t DEADBAND = 100;  // keep tiny hardware deadband after filtering
  if (std::abs(cmd_left)  < DEADBAND) cmd_left  = 0;
  if (std::abs(cmd_right) < DEADBAND) cmd_right = 0;

  // ---- Idle mode: no CAN when stopped ----
  if (motors_idle_) {
    if (cmd_left != 0 || cmd_right != 0) {
      motors_idle_ = false;
      settle_count_[0] = 0;
      settle_count_[1] = 0;
      // Clear stale TPDO1 cache so first read() after wake gets fresh data
      {
        std::lock_guard<std::mutex> lock(rx_mutex_);
        rx_responses_.erase(TPDO1_BASE + left_id_);
        rx_responses_.erase(TPDO1_BASE + right_id_);
        rx_response_stamps_.erase(TPDO1_BASE + left_id_);
        rx_response_stamps_.erase(TPDO1_BASE + right_id_);
      }
      RCLCPP_INFO(rclcpp::get_logger(LOG), "Motors waking up from idle");
    } else {
      return hardware_interface::return_type::OK;
    }
  }

  bool both_zero = (cmd_left == 0 && cmd_right == 0);

  if (both_zero) {
    // ---- Settling to zero: send a few times then go idle ----
    settle_count_[0]++;
    settle_count_[1]++;

    if (settle_count_[0] <= SETTLE_THRESHOLD) {
      uint8_t data[6];
      uint16_t cw = 0x000F;
      int32_t zero = 0;
      std::memcpy(&data[0], &cw, 2);
      std::memcpy(&data[2], &zero, 4);

      std::string batch;
      batch += slcan_format(RPDO1_BASE + left_id_, data, 6);
      batch += slcan_format(RPDO1_BASE + right_id_, data, 6);
      slcan_send_batch(batch);
    }

    // Check idle
    if (settle_count_[0] >= SETTLE_THRESHOLD) {
      if (!motors_idle_) {
        motors_idle_ = true;
        RCLCPP_INFO(rclcpp::get_logger(LOG),
          "Both motors idle — command traffic stopped");
      }
    }
  } else {
    // ---- MOVING: always send EVERY cycle ----
    settle_count_[0] = 0;
    settle_count_[1] = 0;

    uint8_t data_l[6], data_r[6];
    uint16_t cw = 0x000F;

    std::memcpy(&data_l[0], &cw, 2);
    std::memcpy(&data_l[2], &cmd_left, 4);

    std::memcpy(&data_r[0], &cw, 2);
    std::memcpy(&data_r[2], &cmd_right, 4);

    // Async RPDO: motor applies command immediately on receive
    std::string batch;
    batch += slcan_format(RPDO1_BASE + left_id_, data_l, 6);
    batch += slcan_format(RPDO1_BASE + right_id_, data_r, 6);
    slcan_send_batch(batch);
  }

  return hardware_interface::return_type::OK;
}

// ============================================================
// CANopen over SLCAN
// ============================================================

bool KincoCANopenHW::sdo_write(uint8_t node_id, uint16_t index,
                                uint8_t subindex, int32_t value, uint8_t size)
{
  uint32_t rx_id = SDO_RX_BASE + node_id;

  uint8_t cmd;
  switch (size) {
    case 1: cmd = 0x2F; break;
    case 2: cmd = 0x2B; break;
    default: cmd = 0x23; break;
  }

  uint8_t data[8] = {0};
  data[0] = cmd;
  data[1] = index & 0xFF;
  data[2] = (index >> 8) & 0xFF;
  data[3] = subindex;
  std::memcpy(&data[4], &value, 4);

  // Clear pending
  {
    std::lock_guard<std::mutex> lock(rx_mutex_);
    rx_responses_.erase(rx_id);
  }

  slcan_send(SDO_TX_BASE + node_id, data, 8);

  // Wait for ACK
  auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(300);
  while (std::chrono::steady_clock::now() < deadline) {
    {
      std::lock_guard<std::mutex> lock(rx_mutex_);
      auto it = rx_responses_.find(rx_id);
      if (it != rx_responses_.end() && it->second.size() >= 1) {
        bool ok = (it->second[0] == 0x60);
        rx_responses_.erase(it);
        return ok;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(2));
  }

  RCLCPP_WARN(rclcpp::get_logger(LOG),
    "SDO write timeout: node=%d idx=0x%04X sub=%d", node_id, index, subindex);
  return false;
}

bool KincoCANopenHW::sdo_read(uint8_t node_id, uint16_t index,
                               uint8_t subindex, int32_t & out_value)
{
  uint32_t rx_id = SDO_RX_BASE + node_id;

  uint8_t data[8] = {0};
  data[0] = 0x40;
  data[1] = index & 0xFF;
  data[2] = (index >> 8) & 0xFF;
  data[3] = subindex;

  {
    std::lock_guard<std::mutex> lock(rx_mutex_);
    rx_responses_.erase(rx_id);
  }

  slcan_send(SDO_TX_BASE + node_id, data, 8);

  auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
  while (std::chrono::steady_clock::now() < deadline) {
    {
      std::lock_guard<std::mutex> lock(rx_mutex_);
      auto it = rx_responses_.find(rx_id);
      if (it != rx_responses_.end() && it->second.size() >= 8) {
        if (it->second[0] != 0x80) {
          std::memcpy(&out_value, &it->second[4], 4);
          rx_responses_.erase(it);
          return true;
        }
        rx_responses_.erase(it);
        return false;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  return false;
}

void KincoCANopenHW::nmt_command(uint8_t node_id, uint8_t cmd)
{
  uint8_t data[2] = {cmd, node_id};
  slcan_send(NMT_COBID, data, 2);
}

// ============================================================
// Motor Setup
// ============================================================

void KincoCANopenHW::motor_startup(uint8_t node_id)
{
  int32_t sw = 0;
  if (sdo_read(node_id, OD_STATUSWORD, 0x00, sw)) {
    if (sw & 0x0008) {
      sdo_write(node_id, OD_CONTROLWORD, 0x00, 0x0080, 2);
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
      sdo_write(node_id, OD_CONTROLWORD, 0x00, 0x0000, 2);
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  }

  sdo_write(node_id, OD_CONTROLWORD, 0x00, 0x0006, 2);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  sdo_write(node_id, OD_CONTROLWORD, 0x00, 0x0007, 2);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  sdo_write(node_id, OD_CONTROLWORD, 0x00, 0x000F, 2);
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  RCLCPP_INFO(rclcpp::get_logger(LOG), "Motor node %d: Operation Enabled", node_id);
}

void KincoCANopenHW::motor_set_velocity_mode(uint8_t node_id,
                                              int32_t accel, int32_t decel)
{
  sdo_write(node_id, OD_MODES_OF_OP, 0x00, MODE_PROFILE_VELOCITY, 1);
  sdo_write(node_id, OD_PROFILE_ACCEL, 0x00, std::abs(accel), 4);
  sdo_write(node_id, OD_PROFILE_DECEL, 0x00, std::abs(decel), 4);
  RCLCPP_INFO(rclcpp::get_logger(LOG),
    "Motor node %d: Profile Velocity (accel=%d decel=%d)", node_id, accel, decel);
}

void KincoCANopenHW::motor_map_rpdo1(uint8_t node_id)
{
  // Map RPDO1 for ASYNC mode: motor applies command immediately on receive
  sdo_write(node_id, 0x1400, 1, 0x80000200 + node_id, 4);  // Disable RPDO1
  sdo_write(node_id, 0x1600, 0, 0, 1);                      // Clear mapping
  sdo_write(node_id, 0x1600, 1, 0x60400010, 4);             // Map Controlword (16-bit)
  sdo_write(node_id, 0x1600, 2, 0x60FF0020, 4);             // Map Target Velocity (32-bit)
  sdo_write(node_id, 0x1600, 0, 2, 1);                      // 2 mapped objects
  sdo_write(node_id, 0x1400, 2, 255, 1);                    // Async: apply immediately
  sdo_write(node_id, 0x1400, 1, 0x00000200 + node_id, 4);   // Enable RPDO1
  RCLCPP_INFO(rclcpp::get_logger(LOG),
    "Motor node %d: RPDO1 mapped (Async mode)", node_id);
}

void KincoCANopenHW::motor_send_velocity_pdo(uint8_t node_id, int32_t vel_internal)
{
  uint8_t data[6];
  uint16_t cw = 0x000F;
  std::memcpy(&data[0], &cw, 2);
  std::memcpy(&data[2], &vel_internal, 4);
  slcan_send(RPDO1_BASE + node_id, data, 6);
}

void KincoCANopenHW::motor_map_tpdo1(uint8_t node_id)
{
  // Map TPDO1 (0x180 + NodeID) to send Actual Velocity (0x606C)
  // Async mode with event timer: motor auto-sends every 10ms
  sdo_write(node_id, 0x1800, 1, 0x80000180 + node_id, 4);  // Disable TPDO1
  sdo_write(node_id, 0x1A00, 0, 0, 1);                      // Clear mapping
  sdo_write(node_id, 0x1A00, 1, 0x606C0020, 4);             // Map Actual Velocity (32-bit)
  sdo_write(node_id, 0x1A00, 0, 1, 1);                      // 1 mapped object
  sdo_write(node_id, 0x1800, 2, 255, 1);                    // Async (event-driven)
  sdo_write(node_id, 0x1800, 5, 10, 2);                     // Event timer: 10ms
  sdo_write(node_id, 0x1800, 1, 0x00000180 + node_id, 4);   // Enable TPDO1
  RCLCPP_INFO(rclcpp::get_logger(LOG),
    "Motor node %d: TPDO1 mapped (Actual Velocity, Async 10ms)", node_id);
}

// ============================================================
// Unit Conversion
// ============================================================

int32_t KincoCANopenHW::wheel_rads_to_internal(double rad_per_sec) const
{
  double wheel_rpm = rad_per_sec * 60.0 / (2.0 * M_PI);
  double motor_rpm = wheel_rpm * gear_ratio_;
  return static_cast<int32_t>(motor_rpm * velocity_factor_);
}

double KincoCANopenHW::internal_to_wheel_rads(int32_t internal) const
{
  if (velocity_factor_ == 0) return 0.0;
  double motor_rpm = static_cast<double>(internal) / velocity_factor_;
  double wheel_rpm = motor_rpm / gear_ratio_;
  return wheel_rpm * 2.0 * M_PI / 60.0;
}

}  // namespace kinco_canopen_hw

PLUGINLIB_EXPORT_CLASS(kinco_canopen_hw::KincoCANopenHW,
                       hardware_interface::SystemInterface)
