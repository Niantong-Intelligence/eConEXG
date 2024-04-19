import queue
import time
import traceback
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Literal, Optional, Union

from .data_parser import Parser
from .physical_interface import get_interface, get_sock


class iRecorder(Thread):
    class Dev(Enum):
        SIGNAL = 10
        SIGNAL_START = 11
        IMPEDANCE = 20
        IMPEDANCE_START = 21
        IDLE = 30
        IDLE_START = 31
        TERMINATE = 40
        TERMINATE_START = 41

    def __init__(
        self,
        dev_type: Literal["W8", "W16", "W32", "USB32"],
        fs: Union[Literal[500], Literal[1000], Literal[2000]] = 500,
    ):
        """
        Parameters
        ----------
        dev_type: str
            "W8", "W16", "W32", "USB32"
        fs: int
            sample frequency, only available to USB32
        """
        super().__init__(daemon=True, name="Data collect")

        self.info_q = Queue(128)
        self._socket_flag = 0
        self._save_data = Queue()
        self.__status = iRecorder.Dev.TERMINATE

        if dev_type != "USB32" and fs != 500:
            print("optional fs only available to USB32 devices, set to 500")
            fs = 500
        if fs not in [500, 1000, 2000]:
            raise ValueError("fs should be in 500, 1000 or 2000")
        self.__dev_args = {"channel": 0, "fs": fs, "interface": dev_type}

        if dev_type == "W8":
            self.__dev_args.update({"channel": 8})
        elif dev_type == "W16":
            self.__dev_args.update({"channel": 16})
        elif dev_type == "W32":
            self.__dev_args.update({"channel": 32})
        elif dev_type == "USB32":
            self.__dev_args.update({"channel": 32})
        else:
            raise ValueError("Invalid device type")
        self._interface = get_interface(dev_type)(self.info_q, 5)
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
            self.__dev_args.update({"sock": ret})
            print("dev args:", self.__dev_args)  # start connecting socket
            self.dev = self.dev_sock(self.__dev_args)
            self.parser.batt_val = self.dev.send_heartbeat()
            self._socket_flag = 2
            self.info_q.put(True)
            self.__status = iRecorder.Dev.IDLE_START
            self.parser = Parser(
                self.__dev_args["channel"], self.__dev_args["fs"], self._save_data
            )
            self.start()
        except Exception as e:
            traceback.print_exc()
            self.info_q.put(str(e))
            self._socket_flag = 6
            if self._interface.is_alive():
                self._interface.join()
            raise Exception(str(e))

    def get_devs(self, verbose=False) -> list:
        ret = []
        while not self.info_q.empty():
            info = self.info_q.get()
            if isinstance(info, list):
                if len(info) == 1:
                    print(f"Interface: {info[-1]}")
                    if not verbose:
                        continue
                ret.append(info if verbose else info[-1])
            elif isinstance(info, bool):
                if verbose:
                    ret.append(info)
            elif isinstance(info, str):
                raise Exception(info)
        return ret

    def find_devs(self, duration: Optional[int] = None) -> Optional[list]:
        """
        Parameters
        ----------
        duration: int
            search interval, if not None, block for duration seconds and return found devices,
            if set to None, return immediately, devices can be later acquired by calling get_devs()
        """
        if self.is_alive():
            raise Exception("iRecorder already connected.")
        self._socket_flag = 1
        self._interface.duration = duration
        self._interface.start()
        if duration is not None:
            self._interface.join()
            return self.get_devs()

    def start_acquisition_data(self) -> Optional[True]:
        if self.__status == iRecorder.Dev.TERMINATE:
            return
        self.__status = iRecorder.Dev.SIGNAL_START
        while self.__status not in [iRecorder.Dev.SIGNAL, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status == iRecorder.Dev.SIGNAL:
            return True

    def get_data(self, timeout: Optional[float] = None) -> Optional[list]:
        """
        Parameters
        ----------
        timeout:
            a non-negative number, it blocks at most 'timeout' seconds and return
        """
        if self._socket_flag != 2:
            if self.is_alive():
                self.close_dev()
            raise Exception(f"{self.__get_sock_error()}")
        try:
            data: list = self._save_data.get(block=timeout)
        except queue.Empty:
            return
        while not self._save_data.empty():
            data.extend(self._save_data.get())
        return data

    def stop_acquisition(self):
        if self.__status == iRecorder.Dev.TERMINATE:
            return
        self.__status = iRecorder.Dev.IDLE_START
        while self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)

    def start_acquisition_IMPEDANCE(self) -> Optional[True]:
        if self.__status == iRecorder.Dev.TERMINATE:
            return
        self.__status = iRecorder.Dev.IMPEDANCE_START
        while self.__status not in [iRecorder.Dev.IMPEDANCE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status == iRecorder.Dev.IMPEDANCE:
            return True

    def get_IMPEDANCE(self) -> list:
        if self._socket_flag != 2:
            raise Exception(f"{self.__get_sock_error()}")
        data = []
        while not self._save_data.empty():
            data = self._save_data.get()
        return data

    def close_dev(self):
        if self.__status != iRecorder.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = iRecorder.Dev.TERMINATE_START
            while self.__status != iRecorder.Dev.TERMINATE:
                time.sleep(0.01)
        print("iRecorder disconnected")
        if self._interface.is_alive():
            self._interface.join()
        if self.is_alive():
            self.join()

    def get_battery_value(self):
        return self.parser.batt_val

    def __get_sock_error(self):
        if self._socket_flag == 3:
            warn = "Data transmission timeout."
        elif self._socket_flag == 4:
            warn = "Data/iRecorder.Dev.IMPEDANCE initialization failed."
        elif self._socket_flag == 5:
            warn = "Heartbeat package sent failed."
        else:
            warn = f"Unknown error: {self._socket_flag}"
        return warn

    def __recv_data(self):
        def _clear_queue(data: Queue) -> None:
            data.put(None)
            while data.get() is not None:
                continue

        retry = 0
        while self.__status in [iRecorder.Dev.SIGNAL, iRecorder.Dev.IMPEDANCE]:
            try:
                data = self.dev.recv_socket()
                ret = self.parser.parse_data(data)
                if ret:
                    self._save_data.put(ret)
                    # if self.lsl_stream:
                    #     self.lsl_stream.push_chuck(ret)
                    # if self.bdf_stream:
                    #     self.bdf_stream.write_chuck(ret)
            except Exception:
                traceback.print_exc()
                if (self.__dev_args["interface"] == "W32") and (retry < 1):
                    try:
                        print("Wi-Fi reconnecting...")
                        time.sleep(3)
                        self.dev.close_socket()
                        self.dev = self.dev_sock(self.__dev_args, retry_timeout=2)
                        retry += 1
                        continue
                    except Exception:
                        print("Wi-Fi reconnection failed")
                self._socket_flag = 3
                self.__status = iRecorder.Dev.TERMINATE_START
        try:
            self.dev.stop_recv()
        except Exception:
            if self.__status == iRecorder.Dev.IDLE_START:
                self._socket_flag = 5
            self.__status = iRecorder.Dev.TERMINATE_START
        _clear_queue(self._save_data)
        self.parser.clear_buffer()
        print("Recv thread closed")

    def run(self):
        while self.__status not in [iRecorder.Dev.TERMINATE_START]:
            if self.__status in [
                iRecorder.Dev.SIGNAL_START,
                iRecorder.Dev.IMPEDANCE_START,
            ]:
                print("IMPEDANCE/iRecorder.Dev.SIGNAL START")
                try:
                    if self.__status == iRecorder.Dev.SIGNAL_START:
                        self.dev.start_data()
                        self.parser.imp_flag = False
                        self.__status = iRecorder.Dev.SIGNAL
                    elif self.__status == iRecorder.Dev.IMPEDANCE_START:
                        self.dev.start_impe()
                        self.parser.imp_flag = True
                        self.__status = iRecorder.Dev.IMPEDANCE
                    self.__recv_data()
                except Exception:
                    print("IMPEDANCE/iRecorder.Dev.SIGNAL START FAILED!")
                    self._socket_flag = 4
                    self.__status = iRecorder.Dev.TERMINATE_START
            elif self.__status in [iRecorder.Dev.IDLE_START]:
                timestamp = time.time()
                self.__status = iRecorder.Dev.IDLE
                print("IDLE START")
                continue
            elif self.__status in [iRecorder.Dev.IDLE]:
                if (time.time() - timestamp) < 5:
                    time.sleep(0.1)  # to reduce cpu usage
                    continue
                try:  # heartbeat to keep socket alive and update battery level
                    self.parser.batt_val = self.dev.send_heartbeat()
                    timestamp = time.time()
                    # print("Ah, ah, ah, ah\nStayin' alive, stayin' alive")
                except Exception:
                    traceback.print_exc()
                    self._socket_flag = 5
                    self.__status = iRecorder.Dev.TERMINATE_START
            else:
                print("OOPS")
        try:
            self.dev.close_socket()
        except Exception:
            print("socket close failed")
        self.__status = iRecorder.Dev.TERMINATE
        print("TERMINATED")
