import time
import traceback
from queue import Queue
from threading import Thread
from typing import Literal, Optional, Union

from .data_parser import Parser
from .physical_interface import get_interface, get_sock

SIGNAL = 10
SIGNAL_START = 11
IMPEDANCE = 20
IMPEDANCE_START = 21
IDLE = 30
IDLE_START = 31
TERMINATE = 100
TERMINATE_START = 101


class Value:
    def __init__(self, type_char, value):
        self.type_char = type_char
        self.value = value


class iRecorder(Thread):
    def __init__(
        self,
        dev_type: Literal["W8", "W16", "W32", "USB32"],
        fs: Union[Literal[500], Literal[1000], Literal[2000]] = 500,
    ):
        """
        params:
        - dev_type: str, device type, "W8", "W16", "W32", "USB32"
        - fs: int, sample frequency, available to USB32 devices
        """
        super().__init__(daemon=True, name="Data collect")

        self.device_queue = Queue(128)
        self._socket_flag = Value("i", 0)
        self._save_data = Queue()
        self._status = Value("i", TERMINATE)
        self.__battery = Value("i", -1)

        if dev_type != "USB32" and fs != 500:
            print("optional fs only available to USB32 devices, set to 500")
            fs = 500
        if fs not in [500, 1000, 2000]:
            raise ValueError("fs should be in 500, 1000 or 2000")
        self.sock_args = {"channel": 0, "fs": fs, "interface": dev_type}

        if dev_type == "W8":
            self.sock_args.update({"channel": 8})
        elif dev_type == "W16":
            self.sock_args.update({"channel": 16})
        elif dev_type == "W32":
            self.sock_args.update({"channel": 32})
        elif dev_type == "USB32":
            self.sock_args.update({"channel": 32})
        else:
            raise ValueError("Invalid device type")
        self._interface = get_interface(dev_type)(self.device_queue, 5)
        self.dev_sock = get_sock(dev_type)

    def connect_device(self, addr=""):
        if not addr:
            return
        if self.is_alive():
            raise Exception("iRecorder already connected")
            # connecting physical interface
        try:
            ret = self._interface.connect(addr)
            if not ret:
                raise Exception("Failed to connect physical interface")
            self.sock_args.update({"sock": ret})
            print("dev args:", self.sock_args)  # start connecting socket
            self.dev = self.dev_sock(self.sock_args)
            self.__battery.value = self.dev.send_heartbeat()
            self._socket_flag.value = 2
            self.device_queue.put(True)
            self._status.value = IDLE_START
            self.parser = Parser(
                self.sock_args["channel"], self.sock_args["fs"], self._save_data
            )
            self.start()
        except Exception:
            traceback.print_exc()
            self._socket_flag.value = 6
            if self._interface.is_alive():
                self._interface.join()
            raise Exception("Failed to connect device")

    def get_devices(self, verbose=True):
        ret = []
        while not self.device_queue.empty():
            info = self.device_queue.get()
            if isinstance(info, list):
                ret.append(info if verbose else info[-1])
            elif isinstance(info, str):
                raise Exception(info)
            elif isinstance(info, bool):
                if verbose:
                    ret.append(info)
        return ret

    def find_device(self, duration=None):
        # start searching devie
        if self.is_alive():
            raise Exception("iRecorder already connected.")
        self._socket_flag.value = 1
        self._interface.duration = duration
        self._interface.start()
        if duration is not None:
            self._interface.join()
            return self.get_devices(verbose=False)

    def start_acquisition_data(self) -> Optional[True]:
        if self._status.value == TERMINATE:
            return
        self._status.value = SIGNAL_START
        while self._status.value not in [SIGNAL, TERMINATE]:
            time.sleep(0.01)
        if self._status.value == SIGNAL:
            return True

    def get_data(self):
        if self._socket_flag.value != 2:
            raise Exception(f"{self.__get_sock_error()}")
        data = []
        while not self._save_data.empty():
            data.extend(self._save_data.get())
        return data

    def stop_acquisition(self):
        if self._status.value == TERMINATE:
            return
        self._status.value = IDLE_START
        while self._status.value not in [IDLE, TERMINATE]:
            time.sleep(0.01)

    def start_acquisition_impedance(self) -> Optional[True]:
        if self._status.value == TERMINATE:
            return
        self._status.value = IMPEDANCE_START
        while self._status.value not in [IMPEDANCE, TERMINATE]:
            time.sleep(0.01)
        if self._status.value == IMPEDANCE:
            return True

    def get_impedance(self) -> list:
        if self._socket_flag.value != 2:
            raise Exception(f"{self.__get_sock_error()}")
        data = []
        while not self._save_data.empty():
            data = self._save_data.get(block=False)
        return data

    def close_dev(self):
        if self._status.value != TERMINATE:
            # ensure socket is closed correctly
            self._status.value = TERMINATE_START
            while self._status.value != TERMINATE:
                time.sleep(0.01)
        print("iRecorder disconnected")
        if self._interface.is_alive():
            self._interface.join()
        if self.is_alive():
            self.join()

    def get_battery_value(self):
        return self.__battery.value

    def __get_sock_error(self):
        if self._socket_flag.value == 3:
            warn = "Data transmission timeout."
        elif self._socket_flag.value == 4:
            warn = "Data/Impedance initialization failed."
        elif self._socket_flag.value == 5:
            warn = "Heartbeat package sent failed."
        else:
            warn = f"Unknown error: {self._socket_flag.value}"
        return warn

    def __recv_data(self):
        def _clear_queue(data: Queue) -> None:
            data.put(None)
            while data.get() is not None:
                continue

        retry = 0
        while self._status.value in [SIGNAL, IMPEDANCE]:
            try:
                data = self.dev.recv_socket()
                self.parser.parse_data(data)
            except Exception:
                traceback.print_exc()
                if (self.sock_args["interface"] == "W32") and (retry < 1):
                    try:
                        print("Wi-Fi reconnecting...")
                        time.sleep(3)
                        self.dev.close_socket()
                        self.dev = self.dev_sock(self.sock_args, retry_timeout=2)
                        retry += 1
                        continue
                    except Exception:
                        print("Wi-Fi reconnection failed")
                self._socket_flag.value = 3
                self._status.value = TERMINATE_START
        try:
            self.dev.stop_recv()
        except Exception:
            if self._status.value == IDLE_START:
                self._socket_flag.value = 5
            self._status.value = TERMINATE_START
        _clear_queue(self._save_data)
        self.parser.clear_buffer()
        print("Recv thread closed")

    def run(self):
        while self._status.value not in [TERMINATE_START]:
            if self._status.value in [SIGNAL_START, IMPEDANCE_START]:
                print("IMPEDANCE/SIGNAL START")
                try:
                    if self._status.value == SIGNAL_START:
                        self.dev.start_data()
                        self.parser.imp_flag = False
                        self._status.value = SIGNAL
                    elif self._status.value == IMPEDANCE_START:
                        self.dev.start_impe()
                        self.parser.imp_flag = True
                        self._status.value = IMPEDANCE
                    self.__recv_data()
                except Exception:
                    print("IMPEDANCE/SIGNAL START FAILED!")
                    self._socket_flag.value = 4
                    self._status.value = TERMINATE_START
            elif self._status.value in [IDLE_START]:
                timestamp = time.time()
                self._status.value = IDLE
                print("IDLE START")
                continue
            elif self._status.value in [IDLE]:
                if (time.time() - timestamp) < 5:
                    time.sleep(0.1)  # to reduce cpu usage
                    continue
                try:  # heartbeat to keep socket alive and update battery level
                    self.__battery.value = self.dev.send_heartbeat()
                    timestamp = time.time()
                    # print("Ah, ah, ah, ah\nStayin' alive, stayin' alive")
                except Exception:
                    traceback.print_exc()
                    self._socket_flag.value = 5
                    self._status.value = TERMINATE_START
            else:
                print("OOPS")
        try:
            self.dev.close_socket()
        except Exception:
            print("socket close failed")
        self._status.value = TERMINATE
        print("TERMINATED")
