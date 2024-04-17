import time
import queue
import traceback
from multiprocessing import Process, Queue, Value, Event
from typing import Literal, Union, Optional
from .physical_interface import get_interface, get_sock

SIGNAL = 10
SIGNAL_START = 11
IMPEDANCE = 20
IMPEDANCE_START = 21
IDLE = 30
IDLE_START = 31
TERMINATE = 100
TERMINATE_START = 101


class iRecorder(Process):
    def __init__(
        self,
        dev_type: Literal["W8", "W16", "W32", "USB32"],
        fs: Union[500, 1000, 2000] = 500,
    ):
        """
        params:
        - dev_type: str, device type, "W8", "W16", "W32", "USB32"
        - fs: int, sample frequency, available to USB32 devices
        """
        print("initing iRecorder")
        Process.__init__(self, daemon=True, name="Data collect")

        self.device_queue = Queue(128)
        self._socket_flag = Value("i", 0)
        self._save_data = Queue()
        self._status = Value("i", TERMINATE)
        self.__battery = Value("i", -1)
        self.__halt_flag = Event()

        if dev_type != "USB32" and fs != 500:
            print("fs is only available to USB32 devices, 500 would be used instead.")
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
        self.iface = get_interface(dev_type)

    def connect_device(self, addr=""):  # TODO
        # if hasattr(self, "interface"):
        #     try:
        #         self.interface.join(timeout=1)
        #     finally:
        #         del self.interface

        if not self.__halt_flag.is_set():
            self._save_data.put(addr)
            self.__halt_flag.set()

    def find_device(self, _queue: Optional[queue.Queue] = None, duration=5):
        self.interface = self.iface(_queue, duration)
        if not _queue:
            self.interface.join()
            return self.interface.devs

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
            raise Exception(f"{self.get_sock_error()}")
        data = []
        while True:
            try:
                data.extend(self._save_data.get(block=False))
            except queue.Empty:
                break
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
            raise Exception(f"{self.get_sock_error()}")
        data = []
        while True:
            try:
                data = self._save_data.get(block=False)
            except queue.Empty:
                break
        return data

    def close_dev(self):
        if self._status.value != TERMINATE:
            # ensure socket is closed correctly
            self._status.value = TERMINATE_START
            while self._status.value != TERMINATE:
                time.sleep(0.01)
        print("iRecorder disconnected")
        if self.is_alive():
            self.join()

    def get_battery_value(self):
        return self.__battery.value

    def get_sock_error(self):
        if self._socket_flag.value == 3:
            warn = "Data transmission timeout."
        elif self._socket_flag.value == 4:
            warn = "Data/Impedance initialization failed."
        elif self._socket_flag.value == 5:
            warn = "Heartbeat package sent failed."
        else:
            warn = f"Unknown error: {self._socket_flag.value}"
        return warn

    def run(self):
        from .data_parser import Parser
        from threading import Thread
        import queue


        def _clear_queue(data: queue.Queue) -> None:
            data.put(None)
            while data.get() is not None:
                continue

        def _socket_recv():
            retry = 0
            while self._status.value in [SIGNAL, IMPEDANCE]:
                try:
                    data = self.dev.recv_socket()
                    self.__battery.value = self.parser.parse_data(data, self.data_queue)
                except Exception:
                    traceback.print_exc()
                    if (self.sock_args["interface"] == "Wi-Fi") and (retry < 1):
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
            _clear_queue(self.data_queue)
            _clear_queue(self._save_data)
            self.parser.clear_buffer()
            print("Recv thread closed")
        try:
            # start searching devie
            self._socket_flag.value = 1
            _interface = self.iface(self.device_queue, duration=5)
            _interface.start()
            self.__halt_flag.wait()
            # connecting physical interface
            ret=self._save_data.get()
            self.sock_args.update({"sock": ret})
            if not _interface.connect():
                self._socket_flag.value = 0
                return
            print("dev args:", self.sock_args)  # start connecting socket
            self.dev = self.dev_sock(self.sock_args)
            self.__battery.value = self.dev.send_heartbeat()
            self.device_queue.put(2)
            self._socket_flag.value = 2
        except Exception as e:
            traceback.print_exc()
            try:
                self.dev.close_socket()
            finally:
                self.device_queue.put(str(e))
                self._socket_flag.value = 0
                return
        print("socket connected!")
        self.data_queue = queue.Queue()
        self._status.value = IDLE_START
        self.parser = Parser(chs=self.sock_args["channel"], fs=self.sock_args["fs"])
        self._recv_thread = Thread(target=_socket_recv, daemon=True)
        self._recv_thread.start()

        while True:
            if self._status.value in [SIGNAL_START, IMPEDANCE_START]:
                print("IMPEDANCE/SIGNAL START")
                timestamp = time.time()
                try:
                    if self._status.value == SIGNAL_START:
                        self.dev.start_data()
                        self._status.value = SIGNAL
                    elif self._status.value == IMPEDANCE_START:
                        self.dev.start_impe()
                        self._status.value = IMPEDANCE
                except Exception:
                    print("IMPEDANCE/SIGNAL START FAILED!")
                    self._socket_flag.value = 4
                    self._status.value = TERMINATE_START
                self._recv_thread = Thread(target=_socket_recv, daemon=True)
                self._recv_thread.start()
            elif self._status.value in [SIGNAL, IMPEDANCE]:
                try:
                    data = self.data_queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                if self._status.value == SIGNAL:
                    self._save_data.put(data)
                elif self._status.value == IMPEDANCE:
                    self.parser.cal_imp(data, self._save_data)
            elif self._status.value in [IDLE_START, TERMINATE_START]:
                self._recv_thread.join()
                if self._status.value == IDLE_START:
                    timestamp = time.time()
                    self._status.value = IDLE
                    print("IDLE START")
                    continue
                try:
                    self.dev.close_socket()
                    print("socket closed")
                except Exception:
                    print("socket close failed")
                self._status.value = TERMINATE
                print("TERMINATED")
                return
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
