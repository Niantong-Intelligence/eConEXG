from serial import Serial
import time


class iFocus:
    def __init__(self, port) -> None:
        self.delay = 0.1
        self.dev = Serial(port=port, baudrate=921600,timeout=3)
        time.sleep(self.delay)

    def connect_socket(self):
        self.dev.write(b"\x01")
        time.sleep(self.delay * 10)
        if not self.dev.in_waiting:
            raise Exception

    def recv_socket(self, buffersize: int = 30):
        return self.dev.read(buffersize)

    def close_socket(self):
        self.dev.write(b"\x02")
        time.sleep(self.delay)
        self.dev.close()
        self.dev = None
        time.sleep(self.delay)


class econAlpha:
    def __init__(self, port) -> None:
        self.delay = 0.1
        self.dev = Serial(port=port, baudrate=460800,timeout=3)
        time.sleep(self.delay)

    def connect_socket(self):
        self.dev.write(b"\x02")
        time.sleep(self.delay * 10)
        if not self.dev.in_waiting:
            raise Exception

    def recv_socket(self, buffersize: int = 30):
        return self.dev.read(buffersize)

    def close_socket(self):
        self.dev.write(b"\x01")
        time.sleep(self.delay)
        self.dev.close()
        self.dev = None
        time.sleep(self.delay)
