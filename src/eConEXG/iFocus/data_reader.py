import time
from multiprocessing import Process, Queue, Value
from typing import Literal
from serial.tools.list_ports import comports

CAP_SIGNAL = 10
CAP_END = 101
CAP_TERMINATED = 102


class iFocus(Process):
    @staticmethod
    def get_device(dev_type: Literal["EEG", "EMG"] = "EMG"):
        devices = list(comports())
        if dev_type == "EMG":
            for device in devices:
                if "FTDI" in device.manufacturer:
                    if device.serial_number in ["IFOCUSA", "iFocus"]:
                        continue
                    return device.device
        else:
            for device in devices:
                if "FTDI" in device.manufacturer:
                    if device.serial_number in ["IFOCUSA", "iFocus"]:
                        return device.device
        return None

    def __init__(
        self, port, socket_flag: Value, dev_type: Literal["EEG", "EMG"] = "EMG"
    ):
        print("initing device")
        Process.__init__(self, daemon=True)
        self.port = port
        self.socket_flag = socket_flag
        self.dev_type = dev_type
        self.bat = Value("i", -1)
        self.__raw_data = Queue()
        self.__cap_status = Value("i", CAP_TERMINATED)
        self.start()

    def get_battery_value(self):
        if (self.bat.value < 0) or (self.bat.value > 100):
            self.bat.value = -1
        return self.bat.value

    def get_data(self):
        data = []
        while not self.__raw_data.empty():
            temp = self.__raw_data.get()
            data.append(temp)
        return data  # (length, channels)

    def close_cap(self):
        if self.__cap_status.value == CAP_TERMINATED:
            return
        # ensure socket is closed correctly
        self.__cap_status.value = CAP_END
        while self.__cap_status.value != CAP_TERMINATED:
            time.sleep(0.05)

    def __socket_recv(self):
        while self.__cap_status.value in [CAP_SIGNAL]:
            try:
                data = self.__socket.recv_socket()
                if not len(data):
                    raise Exception
                self.__recv_queue.put(data)
            except Exception:
                self.socket_flag.value = 3
                self.__cap_status.value = CAP_END

    def run(self):
        import queue
        import threading
        import traceback

        if self.dev_type == "EMG":
            from .emgParser import Parser
            from .device_socket import econAlpha as dev
        else:
            from .eegParser import Parser
            from .device_socket import iFocus as dev
        print("port:", self.port)
        try:
            self.__socket = dev(port=self.port)
            self.__socket.connect_socket()
        except Exception:
            traceback.print_exc()
            try:
                self.__socket.close_socket()
            except Exception:
                pass
            self.socket_flag.value = 4
            time.sleep(0.1)
            return
        print("device connected!")
        self._parser = Parser(self.bat)
        self.__recv_queue = queue.Queue()
        self.__cap_status.value = CAP_SIGNAL
        self.__recv_thread = threading.Thread(target=self.__socket_recv, daemon=True)
        self.__recv_thread.start()
        while True:
            time.sleep(0.01)
            if self.__cap_status.value == CAP_SIGNAL:
                while not self.__recv_queue.empty():
                    data = self.__recv_queue.get()
                    data_list = self._parser.parse(data)
                    if len(data_list):
                        for data in data_list:
                            self.__raw_data.put(data)
                    if self.__cap_status.value != CAP_SIGNAL:
                        break
            elif self.__cap_status.value == CAP_END:
                self.__recv_thread.join()
                try:
                    self.__socket.close_socket()
                finally:
                    self.__cap_status.value = CAP_TERMINATED
                    print("device closed")
                    return
            else:
                pass
