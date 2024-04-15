from serial.tools.list_ports import comports
from serial import Serial
import time


class com_socket:
    order = {
        "R": b"\x01",
        "W": b"\x05",
        "T": b"\x04",
        "A": b"\x02",
        "B": b"\x07",
        "shock": b"\x08",
        "close": b"\x01",
    }

    @staticmethod
    def devce_list():
        return list(comports())

    def __init__(self, port) -> None:
        self.__socket = Serial(port=port, baudrate=921600)

    def connect_socket(self):
        time.sleep(0.1)
        self.__socket.read_all()

    def close_socket(self):
        self.__socket.write(self.order["R"])
        time.sleep(0.1)
        self.__socket = None
        print("socket closed")
        time.sleep(0.1)

    def start_data(self, imu: bool = True):
        self.__socket.reset_input_buffer()
        if imu:
            self.__socket.write(self.order["W"])
        else:
            self.__socket.write(self.order["A"])
        time.sleep(0.1)

    def recv_socket(self, buffersize: int = 466):
        return self.__socket.read(buffersize)

    def stop_recv(self):
        self.__socket.write(self.order["R"])
        time.sleep(0.1)
        self.__socket.read_all()

    def shock(self):
        self.__socket.write(self.order["shock"])

    def send_heartbeat(self):
        self.__socket.write(self.order["B"])
        time.sleep(0.1)
        self.__socket.timeout = 0.3
        ret = self.__socket.read(1)
        self.__socket.timeout = None
        if len(ret) == 0:
            raise Exception
        return ord(ret)
