#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <unordered_map>
#include <chrono>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp_lifecycle/state.hpp"

namespace kinco_canopen_hw
{

// CANopen constants
constexpr uint32_t SDO_TX_BASE = 0x600;
constexpr uint32_t SDO_RX_BASE = 0x580;
constexpr uint32_t NMT_COBID   = 0x000;
constexpr uint32_t SYNC_COBID  = 0x080;
constexpr uint32_t RPDO1_BASE  = 0x200;
constexpr uint32_t TPDO1_BASE  = 0x180;

// DS402 Object Dictionary
constexpr uint16_t OD_CONTROLWORD     = 0x6040;
constexpr uint16_t OD_STATUSWORD      = 0x6041;
constexpr uint16_t OD_MODES_OF_OP     = 0x6060;
constexpr uint16_t OD_TARGET_VELOCITY = 0x60FF;
constexpr uint16_t OD_PROFILE_ACCEL   = 0x6083;
constexpr uint16_t OD_PROFILE_DECEL   = 0x6084;
constexpr uint16_t OD_ACTUAL_VELOCITY = 0x606C;

constexpr uint8_t MODE_PROFILE_VELOCITY = 3;

class KincoCANopenHW : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(KincoCANopenHW)

  // Lifecycle
  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;

  hardware_interface::CallbackReturn on_configure(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_cleanup(
    const rclcpp_lifecycle::State & previous_state) override;

  // Interface exports
  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;
  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

  // Read / Write
  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

  hardware_interface::return_type write(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  // ---- Serial SLCAN ----
  int  serial_fd_{-1};
  bool serial_open(const std::string & port, int baudrate);
  void serial_close();
  void serial_write_str(const std::string & s);
  std::string serial_read_line(int timeout_ms = 100);

  // ---- SLCAN protocol ----
  void slcan_open(int can_speed_code);
  void slcan_close();
  void slcan_send(uint32_t id, const uint8_t* data, uint8_t len);
  std::string slcan_format(uint32_t id, const uint8_t* data, uint8_t len);
  void slcan_send_batch(const std::string & combined);
  bool slcan_recv(uint32_t & id, uint8_t* data, uint8_t & len, int timeout_ms = 100);

  // ---- CANopen helpers ----
  bool sdo_write(uint8_t node_id, uint16_t index, uint8_t subindex,
                 int32_t value, uint8_t size);
  bool sdo_read(uint8_t node_id, uint16_t index, uint8_t subindex,
                int32_t & out_value);
  void nmt_command(uint8_t node_id, uint8_t cmd);

  // ---- Motor helpers ----
  void motor_startup(uint8_t node_id);
  void motor_set_velocity_mode(uint8_t node_id, int32_t accel, int32_t decel);
  void motor_map_rpdo1(uint8_t node_id);
  void motor_map_tpdo1(uint8_t node_id);  // Motor auto-sends velocity
  void motor_send_velocity_pdo(uint8_t node_id, int32_t vel_internal);

  // ---- Conversion ----
  int32_t wheel_rads_to_internal(double rad_per_sec) const;
  double  internal_to_wheel_rads(int32_t internal) const;

  // ---- Parameters ----
  std::string can_channel_;     // e.g., /dev/ttyACM0
  int         serial_baud_{115200};
  uint8_t     left_id_{1};
  uint8_t     right_id_{2};
  int32_t     gear_ratio_{9};
  int32_t     velocity_factor_{2731};
  int32_t     accel_raw_{5000};
  int32_t     decel_raw_{5000};
  bool        use_sync_{true};
  double      cmd_filter_cutoff_hz_{6.0};
  double      feedback_filter_cutoff_hz_{12.0};
  double      odom_filter_cutoff_hz_{20.0};
  double      max_cmd_delta_rad_s2_{8.0};
  double      zero_hyst_enter_rad_s_{0.02};
  double      zero_hyst_exit_rad_s_{0.04};
  int         tpdo_timeout_ms_{120};
  double      wheel_track_m_{0.39};  // for debug omega estimate; match diff_drive wheel_separation

  // ---- State & Command (2 wheels) ----
  double hw_positions_[2] = {0.0, 0.0};
  double hw_velocities_[2] = {0.0, 0.0};
  double hw_commands_[2] = {0.0, 0.0};
  double raw_hw_velocities_[2] = {0.0, 0.0};
  double control_hw_velocities_[2] = {0.0, 0.0};
  double odom_hw_velocities_[2] = {0.0, 0.0};
  double filtered_hw_velocities_[2] = {0.0, 0.0};
  double filtered_hw_commands_[2] = {0.0, 0.0};
  double limited_hw_commands_[2] = {0.0, 0.0};
  bool   zero_latched_[2] = {true, true};
  bool   command_filter_initialized_{false};
  bool   feedback_filter_initialized_{false};

  // ---- Anti-spam: only send PDO when command changes ----
  int32_t last_cmd_left_{0};
  int32_t last_cmd_right_{0};
  int     settle_count_[2] = {0, 0};  // count zero-velocity cycles
  static constexpr int SETTLE_THRESHOLD = 10;  // stop sending after N zero-cycles
  bool    motors_idle_{false};  // true = both motors settled, NO CAN traffic

  // ---- RX thread ----
  std::thread rx_thread_;
  std::atomic<bool> rx_running_{false};
  std::mutex rx_mutex_;
  std::unordered_map<uint32_t, std::vector<uint8_t>> rx_responses_;
  std::unordered_map<uint32_t, std::chrono::steady_clock::time_point> rx_response_stamps_;
  void rx_loop();
};

}  // namespace kinco_canopen_hw
