import queue
import time
import traceback
from multiprocessing import Process, Queue, Value

from .device_socket import com_socket as device_socket

CAP_SIGNAL = 10
CAP_SIGNAL_START = 11
CAP_IDLE = 30
CAP_IDLE_START = 31
CAP_END = 101
CAP_TERMINATED = 102


class iArmBand(Process):
    def __init__(self, port, socket_flag: Value, imu: bool = True, vib: bool = True):
        print("initing iRecorder")
        Process.__init__(self, daemon=True)
        self.socket_flag = socket_flag
        self.__raw_data = Queue(5000)
        self.__cap_status = Value("i", CAP_TERMINATED)
        self.__battery = Value("i", -1)
        self.port = port
        self.band = Value("i", 0)
        self.imu = imu
        self.vib = vib

    def shock_band(self):
        if self.vib:
            self.band.value = 1
        else:
            pass

    @staticmethod
    def get_device():
        devices = device_socket.devce_list()
        for device in devices:  # ECONEMGA for windows
            if device.serial_number in ["ECONEMGA", "eConEMG"]:
                try:
                    conn = device_socket(device.device)
                    conn.close_socket()
                except Exception:
                    continue
                return device.device
        return None

    def start_acquisition_data(self):
        if self.__cap_status.value == CAP_TERMINATED:
            return
        self.__cap_status.value = CAP_SIGNAL_START
        while self.__cap_status.value != CAP_SIGNAL:
            continue

    def get_data(self):
        data = []
        try:
            while not self.__raw_data.empty():
                temp = self.__raw_data.get(block=False)
                data.append(temp)
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()
        return data  # (channels, length)

    def stop_acquisition(self):
        if self.__cap_status.value == CAP_TERMINATED:
            return
        self.__cap_status.value = CAP_IDLE_START
        while self.__cap_status.value != CAP_IDLE:
            continue

    def close_cap(self):
        if self.__cap_status.value == CAP_TERMINATED:
            return
        # ensure socket is closed correctly
        self.__cap_status.value = CAP_END
        while self.__cap_status.value != CAP_TERMINATED:
            time.sleep(0.05)

    def get_battery_value(self):
        return self.__battery.value

    def socket_recv(self):
        while self.__run_flag:
            if not self.__recv_run_flag:
                time.sleep(0.2)
                continue
            try:
                data = self.__socket.recv_socket()
                if len(data) != 0:
                    self.__recv_queue.put(data)
                else:
                    time.sleep(0.01)
            except Exception:
                print("damn")
                time.sleep(0.2)
                traceback.print_exc()

    def run(self):
        print("port", self.port)
        import threading

        from .data_parser import Parser

        self.socket_flag.value = 1
        self.__socket = device_socket(self.port)
        try:
            self.__socket.connect_socket()
            self.__socket.stop_recv()
            self.__battery.value = self.__socket.send_heartbeat()
        except Exception:
            traceback.print_exc()
            self.socket_flag.value = 4
            self.__socket.close_socket()
            return

        print("cap socket connected!")
        self.sys_data = 0
        self.__timestamp = time.time()
        self.__recv_queue = queue.Queue()
        self.__cap_status.value = CAP_SIGNAL_START
        self.__parser = Parser(self.imu)
        self.__run_flag = True
        self.__recv_run_flag = False
        self.__recv_thread = threading.Thread(target=self.socket_recv, daemon=True)
        self.__recv_thread.start()
        self.socket_flag.value = 2
        self.shock_band()
        while True:
            if self.__cap_status.value == CAP_SIGNAL_START:
                print("CAP_SIGNAL_START")
                self.__parser.clear_buffer()
                while not self.__raw_data.empty():
                    try:
                        self.__raw_data.get(block=False)
                    except queue.Empty:
                        print("Process queue bug caught")
                while not self.__recv_queue.empty():
                    try:
                        self.__recv_queue.get(block=False)
                    except queue.Empty:
                        print("Thread queue bug caught")
                try:
                    self.__recv_run_flag = True
                    self.__socket.start_data(self.imu)
                    self.__cap_status.value = CAP_SIGNAL
                    self.__timestamp = time.time()
                except Exception:
                    traceback.print_exc()
                    self.socket_flag.value = 6
                    self.__cap_status.value = CAP_END
            elif self.__cap_status.value == CAP_SIGNAL:
                try:
                    data = self.__recv_queue.get(timeout=0.02)
                    data_list = self.__parser.parse_data(data)
                    if len(data_list) < 1:
                        continue
                    # shock device if set
                    if self.band.value == 1:
                        self.__socket.shock()
                        self.band.value = 0

                    self.__timestamp = time.time()
                    for data in data_list:
                        data[Parser.HOTKEY_TRIGGER] = self.sys_data
                        self.sys_data = 0
                        self.__battery.value = data[Parser.BATTERY]
                        self.__raw_data.put(
                            data[0 : Parser.BATTERY], block=False
                        )  # assure complete collection
                except queue.Full:
                    print(">>>queue full<<<")
                    self.socket_flag.value = 9
                    self.__cap_status.value = CAP_END
                except Exception:
                    if (time.time() - self.__timestamp) > 4:
                        self.socket_flag.value = 3
                        self.__cap_status.value = CAP_END

            elif self.__cap_status.value == CAP_IDLE_START:
                try:
                    print("CAP_IDLE_START")
                    print("DROPPED PACKETS COUNT:", self.__parser.packet_drop_count)
                    self.__recv_run_flag = False
                    self.__socket.stop_recv()
                    self.__cap_status.value = CAP_IDLE
                    self.__timestamp = time.time()
                except Exception:
                    traceback.print_exc()
                    self.socket_flag.value = 6
                    self.__cap_status.value = CAP_END
            elif self.__cap_status.value == CAP_IDLE:
                time.sleep(0.1)
                if (time.time() - self.__timestamp) > 5:
                    try:
                        self.__battery.value = self.__socket.send_heartbeat()
                        # heartbeat to keep socket alive
                        self.__timestamp = time.time()
                        print("Ah, ah, ah, ah\nStayin' alive, stayin' alive")
                    except Exception:
                        traceback.print_exc()
                        self.socket_flag.value = 5
                        self.__cap_status.value = CAP_END
            elif self.__cap_status.value == CAP_END:
                print("CAP_END")
                self.__recv_run_flag = False
                self.__run_flag = False
                time.sleep(0.1)
                self.__recv_thread.join(timeout=0)
                try:
                    self.__socket.stop_recv()
                except Exception:
                    traceback.print_exc()
                self.__socket.close_socket()
                self.__cap_status.value = CAP_TERMINATED
                print("CAP_TERMINATED")
                return
            else:
                print("shared value bug, but it's ok")
