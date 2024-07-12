import time


class sock:
    def __init__(self, port) -> None:
        from serial import Serial

        self.delay = 0.1
        self.dev = Serial(port=port, baudrate=921600, timeout=3)
        time.sleep(self.delay)

    @staticmethod
    def _find_devs() -> list:
        from serial.tools.list_ports import comports
        from serial import Serial, serialutil

        ret = []
        devices = comports()
        for device in devices:
            if "FTDI" in device.manufacturer:
                if device.serial_number in ["IFOCUSA", "iFocus"]:
                    try:
                        dev = Serial(port=device.device, baudrate=921600, timeout=1)
                    except serialutil.SerialException:
                        continue
                    dev.close()
                    ret.append(device.device)
        if len(ret) == 0:
            raise Exception("iFocus device not found")
        return ret

    def connect_socket(self):
        self.start_data()
        start = time.time()
        while time.time() - start < 2:
            if self.dev.in_waiting:
                self.stop_recv()
                return
            time.sleep(0.1)
        raise Exception("connection failed, no data available.")

    def recv_socket(self, buffersize: int = 30):
        return self.dev.read(buffersize)

    def start_data(self):
        self.dev.read_all()
        time.sleep(self.delay)
        self.dev.write(b"\x01")
        time.sleep(self.delay)

    def stop_recv(self):
        self.dev.write(b"\x02")
        time.sleep(self.delay)

    def close_socket(self):
        try:
            self.dev.write(b"\x02")
        except Exception:
            pass
        time.sleep(self.delay)
        self.dev.close()
        self.dev = None
        time.sleep(self.delay)
