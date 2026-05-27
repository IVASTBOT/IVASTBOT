# IVASTBOT

## USB Permission for External Camera on Ubuntu 22.04

```bash
sudo cp udev/99-obsensor-libusb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
