import can
import time

def main():
    bus = can.interface.Bus(channel='can0', bustype='socketcan', bitrate=500000)
    
    # Read encoder for ID 0x004
    msg = can.Message(arbitration_id=0x004, data=[0x40, 0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)
    
    start_time = time.time()
    enc_start = None
    while time.time() - start_time < 1.0:
        recv = bus.recv(0.1)
        if recv and recv.arbitration_id == 0x184: # SDO response is 0x580 + NodeID
            # Wait, SDO rx is 0x600 + NodeID (0x604), Tx is 0x584
            pass
