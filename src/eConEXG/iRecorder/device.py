import time

import numpy
import numpy as np
from copy import deepcopy
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Optional, Callable
import traceback

from .data_parser import Parser
from .physical_interface import get_interface, get_sock
from ..utils.ArrayQueue import NPQueue


class iRecorder(Thread):
    class Dev(Enum):
        SIGNAL = 10  # signal transmission mode
        SIGNAL_START = 11
        IMPEDANCE = 20  # impedance transmission mode
        IMPEDANCE_START = 21
        IDLE = 30  # idle mode
        IDLE_START = 31
        TERMINATE = 40  # Init state
        TERMINATE_START = 41

    def __init__(self, dev_type: str):
        """
        Args:
            dev_type: iRecorder device type. available options: Literal["W8", "USB8", "W16", "USB16", "W32", "USB32"]
        Raises:
            Exception: if device type not supported.
            Exception: if adapter not available.
        """
        if dev_type not in {"W8", "USB8", "W16", "USB16", "W32", "USB32"}:
            raise ValueError("Unsupported device type.")
        super().__init__(daemon=True, name=f"iRecorder {dev_type}")
        self.handler = None
        self.__error_message = "Device not connected, please connect first."
        self.__update_func = None
        self.__status = iRecorder.Dev.TERMINATE
        self.__lsl_flag = False
        self.__bdf_flag = False
        self.__dev_args = {"type": dev_type}
        self.__dev_args.update({"channel": self.__get_chs()})

        self.__save_data = NPQueue(ch_len=self.__dev_args["channel"])
        self.__info_q = Queue(128)
        self.__with_q = True
        self.__with_process = False

        self.__parser = Parser(self.__dev_args["channel"])
        self.__interface = get_interface(dev_type, self.__info_q)
        self.__dev_sock = get_sock(dev_type)
        self.__dev_args.update({"AdapterInfo": self.__interface.interface})

        self._bdf_file = None
        self.dev = None

        self.set_frequency()
        self.update_channels()

    def find_devs(self, duration: Optional[int] = None) -> Optional[list]:
        """
        Search for available devices, can only be called once per instance.

        Args:
            duration: Search interval in seconds, blocks for about `duration` seconds and return found devices,
                if set to `None`, return `None` immediately, devices can later be acquired by calling `get_devs()` in a loop.

        Returns:
            Available devices.

        Raises:
            Exception: If search thread already running or iRecorder already connected.
        """
        if self.is_alive():
            raise Exception("iRecorder already connected.")
        if self.__interface.is_alive():
            raise Exception("Search thread already running.")
        self.__interface.start()
        if duration is None:
            return
        start = time.time()
        while time.time() - start < duration:
            time.sleep(0.5)
        self.__finish_search()
        return self.get_devs()

    def get_devs(self, verbose: bool = False) -> list:
        """
        Get available devices. This can be called after `find_devs(duration = None)` in a loop,
            each call will *only* return newly found devices.

        Args:
            verbose: if True, return all available devices information, otherwise only return names for connection,
                if you don't know what this parameter does, just leave it at its default value.

        Returns:
            Newly found devices.

        Raises:
            Exception: adapter not found or not enabled etc.
        """
        ret = []
        time.sleep(0.1)
        while not self.__info_q.empty():
            info = self.__info_q.get()
            if isinstance(info, list):
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

        Returns:
            "SIGNAL": data acquisition mode
            "IMPEDANCE": impedance acquisition mode
            "IDLE": idle mode
            "TERMINATE": device not connected or connection closed.
        """
        return self.__status.name

    def get_dev_info(self) -> dict:
        """
        Get current device information, including device name, hardware channel number, acquired channels, sample frequency, etc.

        Returns:
            A dictionary containing device information, which includes:
                `type`: hardware type;
                `channel`: hardware channel number;
                `AdapterInfo`: adapter used for connection;
                `fs`: sample frequency in Hz;
                `ch_info`: channel dictionary, including channel index and name, can be altered by `update_channels()`.
        """
        return deepcopy(self.__dev_args)

    @staticmethod
    def get_available_frequency(dev_type: str) -> list:
        """Get available sample frequencies of different device types.

        Returns:
            Available sample frequencies in Hz.
        """
        if "USB" in dev_type:
            return [500, 1000, 2000]
        return [500]

    def set_frequency(self, fs: Optional[int] = None):
        """Update device sample frequency, this method should be invoked before `connect_device`.

        Args:
            fs: sample frequency in Hz, if `fs` is set to `None` or not in `get_available_frequency()`,
                it will fall back to the lowest available frequency.

        Raises:
            Exception: Device is already connected.

        New in:
            - now you can set the sample frequency after device connection.
        """
        if self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            warn = "Device acquisition in progress, please `stop_acquisition()` first."
            raise Exception(warn)
        available = self.get_available_frequency(self.__dev_args["type"])
        default = available[0]
        if fs is None:
            fs = default
        if fs not in available:
            print(f"Invalid sample frequency, fallback to {default}Hz")
            fs = default
        self.__dev_args.update({"fs": fs})
        self.__parser._update_fs(fs)
        if self.dev is not None:
            self.dev.set_fs(fs)

    def connect_device(self, addr: str) -> None:
        """
        Connect to device by address, block until connection is established or failed.

        Args:
            addr: device address.

        Raises:
            Exception: if device already connected or connection establishment failed.
        """
        if self.is_alive():
            raise Exception("iRecorder already connected")
        try:
            ret = self.__interface.connect(addr)
            self.__dev_args.update({"name": addr, "sock": ret})
            self.__dev_args.update({"_length": self.__parser.packet_len})
            self.dev = self.__dev_sock(self.__dev_args)
            self.__parser.batt_val = self.dev.send_heartbeat()
            self.__error_message = None
            self.__status = iRecorder.Dev.IDLE_START
            self.start()
        except Exception as e:
            self.__error_message = "Device connection failed."
            self.__finish_search()
            raise e

    def update_channels(self, channels: Optional[dict] = None):
        """
        Update channels to acquire, invoke this method when device is not acquiring data or impedance.

        Args:
            channels: channel number and name mapping, e.g. `{0: "FPz", 1: "Oz", 2: "CPz"}`,
                if `None` is given, reset to all available channels with default names.

        Raises:
            Exception: if data/impedance acquisition in progress.
        """
        if self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            warn = "Device acquisition in progress, please stop_acquisition() first."
            raise Exception(warn)
        if channels is None:
            from .default_config import getChannels

            channels = getChannels(self.__dev_args["channel"])
        self.__dev_args.update({"ch_info": channels})
        ch_idx = [i for i in channels.keys()]
        self.__parser._update_chs(ch_idx)

    def start_acquisition_data(self, with_q: bool = True):
        """
        Send data acquisition command to device, block until data acquisition started or failed.

        Args:
            with_q: if True, signal data will be stored in a queue and **should** be acquired by calling `get_data()` in a loop in case data queue is full.
                if False, data will be passed to out of class functions directly, which is more efficient in multithread and multiprocess(with shared memory).
                data can also be acquired through `open_lsl_stream` and `save_bdf_file`.

        Raises:
            Exception: if device not connected or data acquisition init failed.
        """
        self.__check_dev_status()
        if with_q:
            self.__with_q, self.__with_process = True, False
        else:
            self.__with_q, self.__with_process = False, True
        if self.__status == iRecorder.Dev.SIGNAL:
            return
        if self.__status == iRecorder.Dev.IMPEDANCE:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.SIGNAL_START
        while self.__status not in [iRecorder.Dev.SIGNAL, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def set_update_functions(self, function: Callable[[numpy.array], None] = None) -> None:
        """
        set the out of class function, invoked automatically tp process data when self.__with_process is True.

        Args:
            function: The target function
        """
        self.__update_func = function

    def get_data(
            self, timeout: Optional[float] = 0.02
    ) -> Optional[list[Optional[list]]]:
        """
        Acquire all available data, make sure this function is called in a loop when `with_q` is set to `True` in`start_acquisition_data()`

        Args:
            timeout: Non-negative value, blocks at most `timeout` seconds and return, if set to `None`, blocks until new data is available.

        Returns:
            A list of frames, each frame is a list contains all wanted eeg channels and trigger box channel,
                eeg channels can be updated by `update_channels()`.

        Data Unit:
            - eeg: micro volts (µV)
            - triggerbox: int, from `0` to `255`

        Raises:
            Exception: if device not connected or in data acquisition mode.
        """
        self.__check_dev_status()
        if not self.__with_q:
            return
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        data: list = self.__save_data.get()
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def stop_acquisition(self) -> None:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.

        Raises:
            Exception: if device not connected or acquisition stop failed.
        """
        self.__check_dev_status()
        if self.__status == iRecorder.Dev.IDLE:
            return
        self.__status = iRecorder.Dev.IDLE_START
        while self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def start_acquisition_impedance(self) -> None:
        """
        Send impedance acquisition command to device, block until data acquisition started or failed.

        Raises:
            Exception: if device not connected or impedance acquisition init failed.
        """
        self.__check_dev_status()
        if self.__status == iRecorder.Dev.IMPEDANCE:
            return
        if self.__status == iRecorder.Dev.SIGNAL:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.IMPEDANCE_START
        while self.__status not in [iRecorder.Dev.IMPEDANCE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def get_impedance(self) -> Optional[list]:
        """
        Acquire channel impedances, return immediately, impedance update interval is about 2000ms.

        Returns:
            A list of channel impedance ranging from `0` to `np.inf` if available, otherwise `None`.

        Data Unit:
            - impedance: ohm (Ω)
        """
        self.__check_dev_status()
        return self.__parser.impedance

    def close_dev(self) -> None:
        """
        Close device connection and release resources, resources are automatically released on device error.
        """
        if self.__status != iRecorder.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = iRecorder.Dev.TERMINATE_START
            while self.__status != iRecorder.Dev.TERMINATE:
                time.sleep(0.01)
        if self.is_alive():
            self.join()

    def get_packet_drop_times(self) -> int:
        """
        Retrieve packet drop times.
        This value accumulates during data transmission and will be reset to `0` after device status change.

        Returns:
            accumulated packet drop times.
        """
        return self.__parser._drop_count

    def get_battery_value(self) -> int:
        """
        Query battery level.

        Returns:
            battery level in percentage, range from `0` to `100`.
        """
        return self.__parser.batt_val

    def open_lsl_stream(self):
        """
        Open LSL stream, can be invoked after `start_acquisition_data()`,
            each frame is the same as described in `get_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            importError: if `pylsl` not installed or liblsl not installed on unix like system.
        """
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, "_lsl_stream"):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        self._lsl_stream = lslSender(
            self.__dev_args["ch_info"],
            f"iRe{self.__dev_args['type']}_{self.__dev_args['name'][-2:]}",
            "EEG",
            self.__dev_args["fs"],
            with_trigger=True,
        )
        self.__lsl_flag = True

    def close_lsl_stream(self):
        """
        Close LSL stream manually, invoked automatically after `stop_acquisition()` or `close_dev()`
        """
        self.__lsl_flag = False
        if hasattr(self, "_lsl_stream"):
            del self._lsl_stream

    def create_bdf_file(self, filename: str):
        """
        Create a BDF file and save data to it, invoke it after `start_acquisition_data()`.

        Args:
            filename: file name to save data, accept absolute or relative path.

        Raises:
            Exception: if data acquisition not started or `save_bdf_file` is invoked and BDF file already created.
            OSError: if BDF file creation failed, this may be caused by invalid file path or permission issue.
            importError: if `pyedflib` is not installed.
        """
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started")
        if self._bdf_file is not None:
            raise Exception("BDF file already created.")
        from ..utils.bdfWrapper import bdfSaverIRecorder

        if filename[-4:].lower() != ".bdf":
            filename += ".bdf"
        self._bdf_file = bdfSaverIRecorder(
            filename,
            self.__dev_args["ch_info"],
            self.__dev_args["fs"],
            f"iRecorder_{self.__dev_args['type']}_{self.__dev_args['name']}",
        )
        self.__bdf_flag = True

    def close_bdf_file(self):
        """
        Close and save BDF file manually, invoked automatically after `stop_acquisition()` or `close_dev()`
        """
        self.__bdf_flag = False
        if self._bdf_file is not None:
            self._bdf_file.close_bdf()
            self._bdf_file = None

    def send_bdf_marker(self, marker: str):
        """
        Send marker to BDF file, can be invoked after `create_bdf_file()`, otherwise it will be ignored.

        Args:
            marker: marker string to write.
        """
        if self._bdf_file is not None:
            self._bdf_file.write_Annotation(marker)

    # def set_callback_handler(self, handler: Callable[[Optional[str]], None]):
    #     """
    #     Set callback handler function, invoked automatically when device thread ended if set.

    #     Args:
    #         handler: a callable function that takes a string of error message or `None` as input.
    #     """
    #     self.handler = handler

    def __check_dev_status(self):
        if self.__error_message is None:
            return
        if self.is_alive():
            self.close_dev()
        raise Exception(self.__error_message)

    def run(self):
        while self.__status not in [iRecorder.Dev.TERMINATE_START]:
            if self.__status == iRecorder.Dev.SIGNAL_START:
                self.__recv_data(imp_mode=False)
            elif self.__status == iRecorder.Dev.IMPEDANCE_START:
                self.__recv_data(imp_mode=True)
            elif self.__status in [iRecorder.Dev.IDLE_START]:
                self.__idle_state()
            else:
                self.__error_message = f"Unknown status: {self.__status}"
                break
        try:
            self.dev.close_socket()
        except Exception:
            pass
        finally:
            self.__finish_search()
            self.__status = iRecorder.Dev.TERMINATE
        # if self.handler is not None:
        #     self.handler(self.__error_message)

    def __recv_data(self, imp_mode=True):
        self.__parser.imp_flag = imp_mode
        retry = 0
        try:
            if imp_mode:
                self.dev.start_impe()
                self.__status = iRecorder.Dev.IMPEDANCE
                print("IMPEDANCE START")
            else:
                self.dev.start_data()
                self.__status = iRecorder.Dev.SIGNAL
                print("SIGNAL START")
        except Exception:
            self.__error_message = "Data/Impedance mode initialization failed."
            self.__status = iRecorder.Dev.TERMINATE_START
        # recv data
        while self.__status in [iRecorder.Dev.SIGNAL, iRecorder.Dev.IMPEDANCE]:
            try:
                data = self.dev.recv_socket()
                if not data:
                    raise Exception("Remote end closed.")
                ret = self.__parser.parse_data(data)
                if ret:
                    if self.__with_q:
                        self.__save_data.put(ret)
                    elif self.__with_process:
                        ret_array = np.array(ret).T
                        if ret_array.size > 0:
                            self.__update_func(ret_array)
                    if self.__bdf_flag:
                        self._bdf_file.write_chunk(ret)
                    if self.__lsl_flag:
                        self._lsl_stream.push_chunk(ret)
            except Exception:
                traceback.print_exc()
                if (self.__dev_args["type"] == "W32") and (retry < 1):
                    try:
                        print("Wi-Fi reconnecting...")
                        self.dev.close_socket()
                        self.dev = self.__dev_sock(self.__dev_args, retry_timeout=3)
                        retry += 1
                        continue
                    except Exception:
                        print("Wi-Fi reconnection failed")
                self.__error_message = "Data transmission timeout."
                self.__status = iRecorder.Dev.TERMINATE_START
        # postprocess
        self.close_bdf_file()
        self.close_lsl_stream()
        self.__parser.clear_buffer()
        while not self.__save_data.empty():
            self.__save_data.get()
        # stop recv data
        if self.__status != iRecorder.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception:
                if self.__status == iRecorder.Dev.IDLE_START:
                    self.__error_message = "Device connection lost."
                self.__status = iRecorder.Dev.TERMINATE_START

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
                self.__error_message = "Device connection lost."
                self.__status = iRecorder.Dev.TERMINATE_START

    def __get_chs(self) -> int:
        return int("".join([i for i in self.__dev_args["type"] if i.isdigit()]))

    def __finish_search(self):
        if self.__interface.is_alive():
            self.__interface.stop()
            self.__interface.join()
        while not self.__info_q.empty():
            self.__info_q.get()
