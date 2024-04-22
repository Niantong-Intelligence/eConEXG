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
        self.__info_q = Queue(128)
        self.__socket_flag = 1
        self.__save_data = Queue()
        self.__status = iRecorder.Dev.TERMINATE
        self.__lsl_flag = False
        self.__bdf_flag = False
        self.__dev_args = {"channel": 0, "fs": fs, "interface": dev_type}
        self.__validate_dev(dev_type, fs)
        self.__parser = Parser(self.__dev_args["channel"], self.__dev_args["fs"])
        self.update_channels()
        self._interface = get_interface(dev_type)(self.__info_q)
        self.dev_sock = get_sock(dev_type)

    def find_devs(self, duration: Optional[int] = None) -> Optional[list]:
        """
        Search for available devices.
        Parameters
        ----------
        duration: int
            search interval, if not None, block for about duration seconds and return found devices,
            if set to None, return immediately, devices can be later acquired by calling `get_devs()`.
        """
        if self.is_alive():
            raise Exception("iRecorder already connected.")
        if self._interface.is_alive():
            raise Exception("Search thread already running.")
        self._interface.start()
        if duration is None:
            return
        start = time.time()
        while time.time() - start < duration:
            time.sleep(0.5)
        self.__finish_search()
        return self.get_devs()

    def get_devs(self, verbose=False) -> list:
        """
        Get available devices, can be called after `find_devs(duration = None)`, each call will only return newly found devices.

        Parameters
        ----------
        verbose: bool
            if True, return all available devices information, otherwise only return names for connection.
        """
        ret = []
        while not self.__info_q.empty():
            info = self.__info_q.get()
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

    def get_dev_status(self) -> str:
        """
        Get current device status.
        """
        return self.__status.name

    def get_dev_info(self) -> dict:
        """
        Get current device information, including device name, hardware channel number, acquired channels, sample frequency, etc.
        """
        from copy import deepcopy

        return deepcopy(self.__dev_args)

    def connect_device(self, addr: str) -> tuple[Literal[False], str] | Literal[True]:
        """
        Connect to device by address, block until connection is established or failed.

        Returns
        -------
        True if connection is established, otherwise False with error message.
        """
        if self.is_alive():
            raise Exception("iRecorder already connected")
        try:
            ret = self._interface.connect(addr)
            self.__dev_args.update({"name": addr[-2:], "sock": ret})
            self.dev = self.dev_sock(self.__dev_args)
            self.__parser.batt_val = self.dev.send_heartbeat()
            self.__socket_flag = 0
            self.__info_q.put(True)
            self.__status = iRecorder.Dev.IDLE_START
            self.start()
        except Exception as e:
            self.__info_q.put(str(e))
            self.__socket_flag = 2
            self.__finish_search()
            raise e

    def update_channels(self, channels: Optional[dict] = None):
        """
        update channel information, valid only when device stopped acquisition.
        channel number is 0 based.
        Parameters
        ----------
        channels: dict or None
            channel number and name mapping, e.g. {0: "FPz", 1: "Oz", 2: "CPz"},
            if None is given, all channels availabel will be used with default name Ch0, Ch1,..
        """
        if self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            raise Exception("Device acquisition in progress, please stop first.")
        if channels is None:
            channels = {i: f"Ch{i}" for i in range(self.__dev_args["channel"])}
        self.__dev_args.update({"ch_info": channels})
        ch_idx = [i for i in channels.keys()]
        self.__parser.update_chs(ch_idx)

    def start_acquisition_data(self) -> Optional[True]:
        """
        Send data acquisition command to device, block until data acquisition started or failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        if self.__status == iRecorder.Dev.SIGNAL:
            return True
        if self.__status == iRecorder.Dev.IMPEDANCE:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.SIGNAL_START
        while self.__status not in [iRecorder.Dev.SIGNAL, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.SIGNAL:
            self.__raise_sock_error()

    def get_data(self, timeout: Optional[float] = None) -> Optional[list]:
        """
        Aquire amplifier data, each return list of frames, each frame contains all wanted channels and triggerbox data.

        Make sure this function is called in a loop so that it can continuously read the data.

        Parameters
        ----------
        timeout:
            a non-negative number, it blocks at most 'timeout' seconds and return.
        """
        if self.__socket_flag:
            self.__raise_sock_error()
        try:
            data: list = self.__save_data.get(block=timeout)
        except queue.Empty:
            return
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def stop_acquisition(self) -> Optional[True]:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        self.__status = iRecorder.Dev.IDLE_START
        while self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.IDLE:
            self.__raise_sock_error()

    def start_acquisition_impedance(self) -> Optional[True]:
        """
        Send impedance acquisition command to device, block until data acquisition started or failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        if self.__status == iRecorder.Dev.IMPEDANCE:
            return True
        if self.__status == iRecorder.Dev.SIGNAL:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.IMPEDANCE_START
        while self.__status not in [iRecorder.Dev.IMPEDANCE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.IMPEDANCE:
            self.__raise_sock_error()

    def get_impedance(self) -> Optional[list]:
        """
        Aquire channel impedances, return immediatly, impedance update interval is about 2000ms
        """
        if self.__socket_flag:
            if self.is_alive():
                self.close_dev()
            self.__raise_sock_error()
        return self.__parser.impedance

    def close_dev(self):
        """
        Close device connection and release resources.
        """
        if self.__status != iRecorder.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = iRecorder.Dev.TERMINATE_START
            while self.__status != iRecorder.Dev.TERMINATE:
                time.sleep(0.01)
        self.__finish_search()
        if self.is_alive():
            self.join()

    def get_battery_value(self) -> int:
        """
        Query battery level.

        Returns
        -------
        battery level in percentage, range from 0 to 100.
        """
        return self.__parser.batt_val

    def open_lsl_stream(self):
        """
        Open LSL stream, can be invoked after `start_acquisition_data()`
        """
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, "_lsl_stream"):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        self._lsl_stream = lslSender(
            self.__dev_args["ch_info"],
            f"iRe{self.__dev_args['interface']}_{self.__dev_args["name"]}",
            "EEG",
            self.__dev_args["fs"],
            with_trigger=True,
        )
        self.__lsl_flag = True

    def close_lsl_stream(self):
        """
        Close LSL stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_flag = False
        if hasattr(self, "_lsl_stream"):
            del self._lsl_stream

    def save_bdf_file(self, filename: str):
        """
        Save data to BDF file, can be invoked after `start_acquisition_data()`

        Parameters
        ----------
        filename: str
            file name to save data, accept absolute or relative path.
        """
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started")
        if hasattr(self, "_bdf_file"):
            raise Exception("BDF file already created.")
        from ..utils.bdfWrapper import bdfSaver

        if filename[-4:].lower() != ".bdf":
            filename += ".bdf"
        self._bdf_file = bdfSaver(
            filename,
            self.__dev_args["ch_info"],
            self.__dev_args["fs"],
            f"iRecorder{self.__dev_args['interface']}",
        )
        self.__bdf_flag = True

    def close_bdf_file(self):
        """
        Close and save BDF file manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__bdf_flag = False
        if hasattr(self, "_bdf_file"):
            self._bdf_file.close_bdf()
            del self._bdf_file

    def send_bdf_marker(self, marker: str):
        """
        Send marker to BDF file, can be invoked after `open_bdf_file()`
        """
        self._bdf_file.write_Annotation(marker)

    def __raise_sock_error(self):
        if self.__socket_flag == 0:
            return
        if self.is_alive():
            self.close_dev()
        if self.__socket_flag == 1:
            raise Exception("Device not connected, please connect first.")
        elif self.__socket_flag == 2:
            raise Exception("Device connection failed.")
        elif self.__socket_flag == 3:
            raise Exception("Data transmission timeout.")
        elif self.__socket_flag == 4:
            raise Exception("Data/Impedance mode initialization failed.")
        elif self.__socket_flag == 5:
            raise Exception("Heartbeat package sent failed.")
        else:
            raise Exception(f"Unknown error: {self.__socket_flag}")

    def run(self):
        """
        Main loop thread for device status control, invoked automatically after `connect_device()` succeeded.
        """
        while self.__status not in [iRecorder.Dev.TERMINATE_START]:
            if self.__status == iRecorder.Dev.SIGNAL_START:
                self.__recv_data(imp_mode=False)
            elif self.__status == iRecorder.Dev.IMPEDANCE_START:
                self.__recv_data(imp_mode=True)
            elif self.__status in [iRecorder.Dev.IDLE_START]:
                self.__idle_state()
            else:
                print(f"Unknown status: {self.__status}")
                break
        try:
            self.dev.close_socket()
        except Exception:
            print("socket close failed")
        finally:
            self.__status = iRecorder.Dev.TERMINATE
            print("iRecorder disconnected")

    def __recv_data(self, imp_mode=True):
        self.__parser.imp_flag = imp_mode
        retry = 0
        try:
            if imp_mode:
                self.dev.start_impe()
                self.__status = iRecorder.Dev.IMPEDANCE
            else:
                self.dev.start_data()
                self.__status = iRecorder.Dev.SIGNAL
        except Exception:
            print("IMPEDANCE/SIGNAL START FAILED!")
            self.__socket_flag = 4
            self.__status = iRecorder.Dev.TERMINATE_START

        print("IMPEDANCE/SIGNAL START")
        while self.__status in [iRecorder.Dev.SIGNAL, iRecorder.Dev.IMPEDANCE]:
            try:
                data = self.dev.recv_socket()
                ret = self.__parser.parse_data(data)
                if ret:
                    self.__save_data.put(ret)
                    if self.__bdf_flag:
                        self._bdf_file.write_chuck(ret)
                    if self.__lsl_flag:
                        self._lsl_stream.push_chuck(ret)
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
                self.__socket_flag = 3
                self.__status = iRecorder.Dev.TERMINATE_START

        # clear buffer
        self.close_bdf_file()
        self.close_lsl_stream()
        self.__parser.clear_buffer()
        self.__save_data.put(None)
        while self.__save_data.get() is not None:
            continue
        # stop recv data
        if self.__status != iRecorder.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception:
                if self.__status == iRecorder.Dev.IDLE_START:
                    self.__socket_flag = 5
                self.__status = iRecorder.Dev.TERMINATE_START
        print("Data thread closed")

    def __idle_state(self):
        timestamp = time.time()
        self.__status = iRecorder.Dev.IDLE
        while self.__status in [iRecorder.Dev.IDLE]:
            if (time.time() - timestamp) < 5:
                time.sleep(0.2)  # to reduce cpu usage
                continue
            try:  # heartbeat to keep socket alive and update battery level
                self.__parser.batt_val = self.dev.send_heartbeat()
                timestamp = time.time()
                # print("Ah, ah, ah, ah\nStayin' alive, stayin' alive")
            except Exception:
                traceback.print_exc()
                self.__socket_flag = 5
                self.__status = iRecorder.Dev.TERMINATE_START

    def __validate_dev(self, dev_type, fs):
        if dev_type != "USB32" and fs != 500:
            print("optional fs only available to USB32 devices, set to 500")
            fs = 500
        if fs not in [500, 1000, 2000]:
            raise ValueError("fs should be in 500, 1000 or 2000")
        self.__dev_args.update({"fs": fs})
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

    def __finish_search(self):
        if self._interface.is_alive():
            self._interface.stop()
            self._interface.join()
