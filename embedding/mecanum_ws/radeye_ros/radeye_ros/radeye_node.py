#!/usr/bin/env python3

from turtle import pen
import rclpy
from rclpy.node import Node
from rclpy import qos

from std_msgs.msg import Float64
import serial

class RadEyeNode(Node):
    def __init__(self):
        super().__init__('radeye_node')

        port = self.declare_parameter('port', '/dev/ttyUSB0').get_parameter_value().string_value
        self.ser = serial.Serial(
            port=port,
            baudrate=9600,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.SEVENBITS,
            xonxoff=False,
            rtscts=False,
            dsrdtr=True
        )
        if self.ser.is_open: self.ser.close()
        self.ser.open()

        self.data_pub = self.create_publisher(
            Float64,
            'dose',
            qos.qos_profile_sensor_data
        )

        self.timer = self.create_timer(1.0, self.timer_cb)
    
    def timer_cb(self):
        out = bytearray()
        while True:
            byte = self.ser.read()
            if byte == b'\x0A': break
            if byte not in [b'\x02', b'\x03']:
                out.extend(byte)
        
        if out == b'@CIAO\r':
            self.get_logger().warn('sensor turning off')
            return

        out = out.decode('ascii').split(' ')
        self.get_logger().debug(f'packet received: {out}')

        if len(out) >= 7:
            dose = float(out[1]) / 100 # in uSv/h
            msg = Float64()
            msg.data = dose
            self.data_pub.publish(msg)
        else:
            self.get_logger().error(f'invalid packet received: {out} - ignored')
    
def main():
    rclpy.init()
    node = RadEyeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    rclpy.shutdown()

if __name__ == '__main__':
    main()

