import time
from typing import Optional


class sock:
    """
    modes=b"MODEN",b"MODET",b"MODES"
    """

    cmd = {
        250: b"SR250",
        500: b"SR500",
        1000: b"SR1000",
        2000: b"SR2000",
        "W": b"START",
        "R": b"PAUSE",
        "Q": b"QUERY",
        "V": b"MOTOR",
    }

    def __init__(self, port, data_len) -> None:
        from serial import Serial

        self.delay = 0.1
        self.dev = Serial(port=port, timeout=3)
        self.data_len = data_len

    def set_frequency(self, fs):
        time.sleep(self.delay)
        try:
            self.dev.write(sock.cmd[fs])
        except KeyError:
            raise NotImplementedError("Invalid sample frequency.")

    @staticmethod
    def find_devs() -> list:
        from serial.tools.list_ports import comports
        from serial import Serial, serialutil

        ret = []
        devices = comports()
        for device in devices:
            if (device.vid == 0x2FE3) and (device.pid == 0x0001):
                try:
                    dev = Serial(port=device.device, timeout=1)
                except serialutil.SerialException:
                    continue
                dev.close()
                ret.append(device.device)
        if len(ret) == 0:
            raise Exception("eConAlpha device not found")
        return ret

    def connect_socket(self):
        try:
            self.dev.flush()
            # time.sleep(self.delay)
            # self.dev.write(self.cmd["Q"])
            # time.sleep(self.delay)
            # ret = self.dev.read_all()
            # print(f"ret {ret}")
            # num = ret.split(b",")[0]
            # if num == b"0":
            #     raise Exception
        except Exception:
            raise Exception("connection failed, no data available.")

    def recv_socket(self, buffer_size: Optional[int] = None):
        if buffer_size is None:
            buffer_size = self.data_len
        return self.dev.read(buffer_size)

    def shock_band(self):
        self.dev.write(self.cmd["V"])
        time.sleep(self.delay)

    def start_data(self):
        self.dev.read_all()
        time.sleep(self.delay)
        self.dev.write(self.cmd["W"])
        time.sleep(self.delay)

    def stop_recv(self):
        self.dev.write(self.cmd["R"])
        time.sleep(self.delay)

    def close_socket(self):
        try:
            self.dev.write(self.cmd["R"])
        except Exception:
            pass
        time.sleep(self.delay)
        self.dev.close()
        self.dev = None
