#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <sensor_msgs/msg/joy.hpp>
#include <memory>
#include <cmath>

class GamepadTeleop : public rclcpp::Node
{
public:
    GamepadTeleop() : Node("omni_robot_gamepad_teleop")
    {
        // Create publisher for velocity commands
        velocity_pub_ = this->create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 1);
        
        // Create safety timer for auto-stop when no input
        safety_timer_ = this->create_wall_timer(
            std::chrono::milliseconds(100), // Check every 100ms
            std::bind(&GamepadTeleop::safetyTimerCallback, this)
        );
        
        // Subscribe to joy messages
        joy_sub_ = this->create_subscription<sensor_msgs::msg::Joy>(
            "/joy", 10, 
            std::bind(&GamepadTeleop::joyCallback, this, std::placeholders::_1)
        );
        
        // Declare parameters for 4-wheel omni robot
        this->declare_parameter("linear_velocity", 0.3);
        this->declare_parameter("angular_velocity", 0.5);
        this->declare_parameter("deadzone", 0.1);
        this->declare_parameter("linear_x_axis", 0);     // Left stick X axis (strafe left/right)
        this->declare_parameter("linear_y_axis", 1);     // Left stick Y axis (forward/backward)
        // Emergency stop now uses L2+R2 triggers (axes 2 and 5)
        // L1 and R1 are now used for rotation in discrete mode
        this->declare_parameter("velocity_step", 0.1);   // Velocity adjustment step
        this->declare_parameter("input_timeout", 0.5);   // Auto-stop timeout in seconds (safety feature)
        
        // Button mappings (standard gamepad layout)
        this->declare_parameter("button_a", 0);         // A button (lower velocity)
        this->declare_parameter("button_b", 1);         // B button (increase angular vel)
        this->declare_parameter("button_x", 2);         // X button (decrease angular vel)
        this->declare_parameter("button_y", 3);         // Y button (increase linear vel)
        
        // D-pad mappings for omni movement (using axes for most gamepads)
        this->declare_parameter("dpad_vertical_axis", 7);   // D-pad up/down axis (forward/backward)
        this->declare_parameter("dpad_horizontal_axis", 6); // D-pad left/right axis (strafe left/right)
        this->declare_parameter("dpad_rotation_button_l", 4); // L1 button for left rotation
        this->declare_parameter("dpad_rotation_button_r", 5); // R1 button for right rotation
        
        // Get parameters
        linear_velocity_ = this->get_parameter("linear_velocity").as_double();
        angular_velocity_ = this->get_parameter("angular_velocity").as_double();
        deadzone_ = this->get_parameter("deadzone").as_double();
        linear_x_axis_ = this->get_parameter("linear_x_axis").as_int();
        linear_y_axis_ = this->get_parameter("linear_y_axis").as_int();
        // Emergency stop now handled by L2+R2 triggers directly in callback
        velocity_step_ = this->get_parameter("velocity_step").as_double();
        input_timeout_ = this->get_parameter("input_timeout").as_double();
        
        button_a_ = this->get_parameter("button_a").as_int();
        button_b_ = this->get_parameter("button_b").as_int();
        button_x_ = this->get_parameter("button_x").as_int();
        button_y_ = this->get_parameter("button_y").as_int();
        dpad_vertical_axis_ = this->get_parameter("dpad_vertical_axis").as_int();
        dpad_horizontal_axis_ = this->get_parameter("dpad_horizontal_axis").as_int();
        dpad_rotation_button_l_ = this->get_parameter("dpad_rotation_button_l").as_int();
        dpad_rotation_button_r_ = this->get_parameter("dpad_rotation_button_r").as_int();
        
        RCLCPP_INFO(this->get_logger(), "4-Wheel Omni Robot Gamepad Teleop Node Started");
        RCLCPP_INFO(this->get_logger(), "Subscribing to /joy topic");
        RCLCPP_INFO(this->get_logger(), "Publishing to /cmd_vel topic");
        RCLCPP_INFO(this->get_logger(), "Linear velocity: %.2f m/s", linear_velocity_);
        RCLCPP_INFO(this->get_logger(), "Angular velocity: %.2f rad/s", angular_velocity_);
        RCLCPP_INFO(this->get_logger(), "Emergency stop: L2+R2 triggers together");
        RCLCPP_INFO(this->get_logger(), "Safety timeout: %.1f seconds (auto-stop when no input)", input_timeout_);
        RCLCPP_INFO(this->get_logger(), "Controls for 4-wheel omni robot:");
        RCLCPP_INFO(this->get_logger(), "  Left stick: Linear movement (X=strafe left/right, Y=forward/backward)");
        RCLCPP_INFO(this->get_logger(), "  D-pad: Discrete movement (Up/Down=forward/backward, Left/Right=strafe)");
        RCLCPP_INFO(this->get_logger(), "  L1/R1: Discrete rotation (left/right)");
        RCLCPP_INFO(this->get_logger(), "  L2+R2: Emergency stop");
        RCLCPP_INFO(this->get_logger(), "  Y button: Increase linear velocity");
        RCLCPP_INFO(this->get_logger(), "  A button: Decrease linear velocity"); 
        RCLCPP_INFO(this->get_logger(), "  B button: Increase angular velocity");
        RCLCPP_INFO(this->get_logger(), "  X button: Decrease angular velocity");
        
        // Initialize safety system
        last_input_time_ = this->now();
        last_warning_time_ = 0.0;
    }

private:
    void joyCallback(const sensor_msgs::msg::Joy::SharedPtr msg)
    {
        // Update last input time for safety timeout
        last_input_time_ = this->now();
        
        geometry_msgs::msg::Twist twist_msg;
        twist_msg.linear.x = 0.0;
        twist_msg.linear.y = 0.0;
        twist_msg.linear.z = 0.0;
        twist_msg.angular.x = 0.0;
        twist_msg.angular.y = 0.0;
        twist_msg.angular.z = 0.0;
        
        // Check for emergency stop buttons (L2 + R2 together for emergency stop)
        bool emergency_stop = false;
        bool l2_pressed = (2 < static_cast<int>(msg->axes.size())) && (msg->axes[2] < -0.5);
        bool r2_pressed = (5 < static_cast<int>(msg->axes.size())) && (msg->axes[5] < -0.5);
        
        if (l2_pressed && r2_pressed) {
            emergency_stop = true;
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000, "Emergency stop active (L2+R2)");
        }
        
        if (emergency_stop) {
            // Send zero velocities for emergency stop
            velocity_pub_->publish(twist_msg);
            return;
        }
        
        // Handle velocity adjustment buttons (only on button press, not hold)
        handleVelocityButtons(msg);
        
        // Check D-pad axes for discrete omni movement
        bool dpad_active = false;
        
        if (dpad_vertical_axis_ < static_cast<int>(msg->axes.size())) {
            if (msg->axes[dpad_vertical_axis_] > 0.5) {  // D-pad up (forward)
                twist_msg.linear.x = linear_velocity_;
                dpad_active = true;
            }
            else if (msg->axes[dpad_vertical_axis_] < -0.5) {  // D-pad down (backward)
                twist_msg.linear.x = -linear_velocity_;
                dpad_active = true;
            }
        }
        
        if (dpad_horizontal_axis_ < static_cast<int>(msg->axes.size())) {
            if (msg->axes[dpad_horizontal_axis_] > 0.5) {  // D-pad right (strafe right)
                twist_msg.linear.y = linear_velocity_;   // Positive Y for right strafe
                dpad_active = true;
            }
            else if (msg->axes[dpad_horizontal_axis_] < -0.5) {  // D-pad left (strafe left)
                twist_msg.linear.y = -linear_velocity_;  // Negative Y for left strafe
                dpad_active = true;
            }
        }
        
        // Check rotation buttons (L1/R1 for discrete rotation)
        if (dpad_rotation_button_l_ < static_cast<int>(msg->buttons.size()) && msg->buttons[dpad_rotation_button_l_]) {
            twist_msg.angular.z = -angular_velocity_;   // Left rotation
            dpad_active = true;
        }
        if (dpad_rotation_button_r_ < static_cast<int>(msg->buttons.size()) && msg->buttons[dpad_rotation_button_r_]) {
            twist_msg.angular.z = angular_velocity_;  // Right rotation
            dpad_active = true;
        }
        
        // If D-pad is not active, check left analog stick for omni movement
        if (!dpad_active) {
            if (linear_x_axis_ < static_cast<int>(msg->axes.size()) && 
                linear_y_axis_ < static_cast<int>(msg->axes.size())) {
                
                double linear_x_input = msg->axes[linear_x_axis_];     // Left stick X (strafe)
                double linear_y_input = msg->axes[linear_y_axis_];     // Left stick Y (forward/backward)
                
                // Apply forward/backward movement
                if (std::abs(linear_y_input) > deadzone_) {
                    twist_msg.linear.x = linear_velocity_ * linear_y_input;
                }
                
                // Apply strafing movement
                if (std::abs(linear_x_input) > deadzone_) {
                    // X axis: pushing right should strafe right (negative Y)
                    twist_msg.linear.y = linear_velocity_ * linear_x_input;
                }
            }
        }
        

        
        velocity_pub_->publish(twist_msg);
    }
    
    void handleVelocityButtons(const sensor_msgs::msg::Joy::SharedPtr msg)
    {
        // Handle Y button (increase linear velocity)
        if (button_y_ < static_cast<int>(msg->buttons.size()) && msg->buttons[button_y_]) {
            if (!prev_button_y_) {  // Only on button press, not hold
                linear_velocity_ = std::min(5.0, linear_velocity_ + velocity_step_);
                RCLCPP_INFO(this->get_logger(), "Linear velocity: %.2f m/s", linear_velocity_);
            }
            prev_button_y_ = true;
        } else {
            prev_button_y_ = false;
        }
        
        // Handle A button (decrease linear velocity)
        if (button_a_ < static_cast<int>(msg->buttons.size()) && msg->buttons[button_a_]) {
            if (!prev_button_a_) {  // Only on button press, not hold
                linear_velocity_ = std::max(0.0, linear_velocity_ - velocity_step_);
                RCLCPP_INFO(this->get_logger(), "Linear velocity: %.2f m/s", linear_velocity_);
            }
            prev_button_a_ = true;
        } else {
            prev_button_a_ = false;
        }
        
        // Handle B button (increase angular velocity)
        if (button_b_ < static_cast<int>(msg->buttons.size()) && msg->buttons[button_b_]) {
            if (!prev_button_b_) {  // Only on button press, not hold
                angular_velocity_ = std::min(5.0, angular_velocity_ + velocity_step_);
                RCLCPP_INFO(this->get_logger(), "Angular velocity: %.2f rad/s", angular_velocity_);
            }
            prev_button_b_ = true;
        } else {
            prev_button_b_ = false;
        }
        
        // Handle X button (decrease angular velocity)
        if (button_x_ < static_cast<int>(msg->buttons.size()) && msg->buttons[button_x_]) {
            if (!prev_button_x_) {  // Only on button press, not hold
                angular_velocity_ = std::max(0.0, angular_velocity_ - velocity_step_);
                RCLCPP_INFO(this->get_logger(), "Angular velocity: %.2f rad/s", angular_velocity_);
            }
            prev_button_x_ = true;
        } else {
            prev_button_x_ = false;
        }
    }
    
    void safetyTimerCallback()
    {
        // Check if too much time has passed since last input
        auto current_time = this->now();
        auto time_since_input = (current_time - last_input_time_).seconds();
        
        if (time_since_input > input_timeout_) {
            // Send zero velocities for safety
            geometry_msgs::msg::Twist zero_twist;
            zero_twist.linear.x = 0.0;
            zero_twist.linear.y = 0.0;
            zero_twist.linear.z = 0.0;
            zero_twist.angular.x = 0.0;
            zero_twist.angular.y = 0.0;
            zero_twist.angular.z = 0.0;
            
            velocity_pub_->publish(zero_twist);
            
            // Log warning every 2 seconds to avoid spam
            if (time_since_input - last_warning_time_ > 2.0) {
                RCLCPP_WARN(this->get_logger(), "Safety timeout: No joystick input for %.1f seconds, stopping robot", time_since_input);
                last_warning_time_ = time_since_input;
            }
        }
    }
    
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr velocity_pub_;
    rclcpp::Subscription<sensor_msgs::msg::Joy>::SharedPtr joy_sub_;
    rclcpp::TimerBase::SharedPtr safety_timer_;
    
    double linear_velocity_;
    double angular_velocity_;
    double deadzone_;
    double velocity_step_;
    double input_timeout_;
    
    // Safety system variables
    rclcpp::Time last_input_time_;
    double last_warning_time_;
    int linear_x_axis_;  // Left stick X for strafing
    int linear_y_axis_;  // Left stick Y for forward/backward
    
    // Button indices
    int button_a_, button_b_, button_x_, button_y_;
    int dpad_vertical_axis_, dpad_horizontal_axis_;
    int dpad_rotation_button_l_, dpad_rotation_button_r_;
    
    // Button state tracking (for edge detection)
    bool prev_button_a_ = false;
    bool prev_button_b_ = false;
    bool prev_button_x_ = false;
    bool prev_button_y_ = false;
    

};

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<GamepadTeleop>();
    
    RCLCPP_INFO(node->get_logger(), "Spinning node...");
    rclcpp::spin(node);
    
    rclcpp::shutdown();
    return 0;
}
