#include <cerrno>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

// 100 ms settling time after the port is configured.
static constexpr useconds_t kSerialSettleUs = 100000;

namespace {

constexpr int kPacketSize = 12;
constexpr int kMaxMotorSpeed = 200;

int clamp_speed(int speed) {
    if (speed < 0) {
        return 0;
    }
    if (speed > kMaxMotorSpeed) {
        return kMaxMotorSpeed;
    }
    return speed;
}

uint8_t byte_mod(int value) {
    return static_cast<uint8_t>(value & 0xFF);
}

int write_all(int fd, const uint8_t* data, int size) {
    int written = 0;
    while (written < size) {
        const ssize_t n = write(fd, data + written, size - written);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        written += static_cast<int>(n);
    }
    return 0;
}

}  // namespace

extern "C" int robot_open(const char* serial_port) {
    if (serial_port == nullptr) {
        return -1;
    }

    const int fd = open(serial_port, O_RDWR | O_NOCTTY | O_SYNC);
    if (fd < 0) {
        return -1;
    }

    termios tty{};
    if (tcgetattr(fd, &tty) != 0) {
        close(fd);
        return -1;
    }

    cfmakeraw(&tty);
    cfsetispeed(&tty, B115200);
    cfsetospeed(&tty, B115200);

    tty.c_cflag = static_cast<unsigned int>((tty.c_cflag & ~CSIZE) | CS8);
    tty.c_cflag |= CLOCAL | CREAD;
    tty.c_cflag &= static_cast<unsigned int>(~(PARENB | PARODD));
    tty.c_cflag &= static_cast<unsigned int>(~CSTOPB);
    tty.c_cflag &= static_cast<unsigned int>(~CRTSCTS);
    tty.c_cflag &= static_cast<unsigned int>(~HUPCL);
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 5;

    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        close(fd);
        return -1;
    }

    usleep(kSerialSettleUs);
    return fd;
}

extern "C" void robot_close(int fd) {
    if (fd >= 0) {
        close(fd);
    }
}

extern "C" int robot_send_raw(
    int fd,
    uint8_t lenh,
    uint8_t malenh,
    int g1,
    int g2,
    int g3,
    int g4,
    int g5,
    int g6,
    int g7,
    int g8,
    int g9,
    int fr) {
    if (fd < 0) {
        return 0;
    }

    const uint8_t packet[kPacketSize] = {
        lenh,
        malenh,
        byte_mod(g1),
        byte_mod(g2),
        byte_mod(g3),
        byte_mod(g4),
        byte_mod(g5),
        byte_mod(g6),
        byte_mod(g7),
        byte_mod(g8),
        byte_mod(g9),
        byte_mod(fr),
    };

    return write_all(fd, packet, kPacketSize) == 0 ? 1 : 0;
}

extern "C" int robot_send_motor(
    int fd,
    int left_dir,
    int left_speed,
    int right_dir,
    int right_speed) {
    left_speed = clamp_speed(left_speed);
    right_speed = clamp_speed(right_speed);

    if (left_speed == 0) {
        left_dir = 0;
    }
    if (right_speed == 0) {
        right_dir = 0;
    }

    return robot_send_raw(
        fd,
        static_cast<uint8_t>('M'),
        0,
        left_dir,
        left_speed,
        right_dir,
        right_speed,
        0,
        0,
        0,
        0,
        0,
        0);
}

extern "C" int robot_stop(int fd) {
    return robot_send_motor(fd, 0, 0, 0, 0);
}
