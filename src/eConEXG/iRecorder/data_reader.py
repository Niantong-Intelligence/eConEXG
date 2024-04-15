import time
import traceback
from multiprocessing import Process, Queue, Value, Event

SIGNAL = 10
SIGNAL_START = 11
IMPEDANCE = 20
IMPEDANCE_START = 21
IDLE = 30
IDLE_START = 31
TERMINATE = 100
TERMINATE_START = 101


class iRecorder(Process):
    def __init__(self, sock_args: dict, socket_flag: Value):  # type: ignore
        print("initing iRecorder")
        Process.__init__(self, daemon=True, name="Data collect")
        self.sock_args = sock_args
        self.device_queue = Queue(128)
        self._socket_flag = socket_flag
        self._save_data = Queue()
        self._status = Value("i", TERMINATE)
        self.__battery = Value("i", -1)
        self.__halt_flag = Event()

    def get_conn_addr(self, addr):
        if not self.__halt_flag.is_set():
            self._save_data.put(addr)
            self.__halt_flag.set()

    def start_acquisition_data(self):
        if self._status.value == TERMINATE:
            return
        self._status.value = SIGNAL_START
        while self._status.value not in [SIGNAL, TERMINATE]:
            time.sleep(0.01)

    def get_data(self):
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

    def start_acquisition_impedance(self):
        if self._status.value == TERMINATE:
            return
        self._status.value = IMPEDANCE_START
        while self._status.value not in [IMPEDANCE, TERMINATE]:
            time.sleep(0.01)

    def get_impedance(self):
        data = []
        while not self._save_data.empty():
            data = self._save_data.get()
        return data

    def close_dev(self):
        if self._status.value != TERMINATE:
            # ensure socket is closed correctly
            self._status.value = TERMINATE_START
            while self._status.value != TERMINATE:
                time.sleep(0.01)
        self._socket_flag.value = 0
        print("iRecorder disconnected")
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
        from data_parser import Parser
        from threading import Thread
        import queue

        if self.sock_args["interface"] == "Wi-Fi":
            from device_socket import wifi_socket as device_socket
            from physical_interface import wifi_util as interface
        elif self.sock_args["interface"] == "Bluetooth":
            from device_socket import bluetooth_socket as device_socket
            from physical_interface import bluetooth_util as interface
        elif self.sock_args["interface"] == "COM":
            from device_socket import com_socket as device_socket
            from physical_interface import com_util as interface
        elif self.sock_args["interface"] == "UWB":
            from device_socket import uwb_socket as device_socket
            from physical_interface import com_util as interface

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
                            self.dev = device_socket(self.sock_args)
                            self.dev.connect_socket(timeout=2)
                            retry += 1
                            continue
                        except Exception:
                            print("Wi-Fi reconnect failed")
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
            _interface = interface.conn(self.device_queue, self.sock_args)
            _interface.start()
            self.__halt_flag.wait()
            # connecting physical interface
            if not _interface.connect(self._save_data.get()):
                self._socket_flag.value = 0
                return
            print("dev args:", self.sock_args)  # start connecting socket
            self.dev = device_socket(self.sock_args)
            self.dev.connect_socket()
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
