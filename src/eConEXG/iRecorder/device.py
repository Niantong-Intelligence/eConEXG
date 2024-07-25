import queue
import time
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Literal, Optional
from datetime import datetime
from .data_parser import Parser
from .physical_interface import get_interface, get_sock


class iRecorder(Thread):
    class Dev(Enum):
        SIGNAL = 10  # signal transmision mode
        SIGNAL_START = 11
        IMPEDANCE = 20  # impedance transmision mode
        IMPEDANCE_START = 21
        IDLE = 30  # idle mode
        IDLE_START = 31
        TERMINATE = 40  # Init state
        TERMINATE_START = 41

    def __init__(self, dev_type: Literal["W8", "USB8", "W16", "USB16", "W32", "USB32"]):
        """
        Args:
            dev_type: iRecorder device type.

        Raises:
            Exception: if device type not supported.
            Exception: if adapter not available.
        """
        if dev_type not in {"W8", "USB8", "W16", "USB16", "W32", "USB32"}:
            raise ValueError("Unsupported device type.")
        super().__init__(daemon=True, name=f"iRecorder {dev_type}")
        self.__info_q = Queue(128)
        self.__socket_flag = 1
        self.__save_data = Queue()
        self.__status = iRecorder.Dev.TERMINATE
        self.__lsl_flag = False
        self.__bdf_flag = False
        self.__dev_args = {"type": dev_type}
        self.__dev_args.update({"channel": self.__get_chs()})

        self.__parser = Parser(self.__dev_args["channel"])
        self.__interface = get_interface(dev_type)(self.__info_q)
        self.__dev_sock = get_sock(dev_type)
        self.__dev_args.update({"AdapterInfo": self.__interface.interface})

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
        from copy import deepcopy

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
                it will fallback to the lowest available frequency.

        Raises:
            Exception: Device is already connected.
        """
        if self.is_alive():
            raise Exception("Set frequency failed, device already connected.")
        available = self.get_available_frequency(self.__dev_args["type"])
        default = available[0]
        if fs is None:
            fs = default
        if fs not in available:
            print(f"Invalid sample frequency, fallback to {default}Hz")
            fs = default
        self.__dev_args.update({"fs": fs})
        self.__parser._update_fs(fs)

    def connect_device(self, addr: str) -> None:
        """
        Connect to device by address, block until connection is established or failed.

        Args:
            addr: device address.

        Raises:
            Exception: if device already connected or connection failed.
        """
        if self.is_alive():
            raise Exception("iRecorder already connected")
        try:
            ret = self.__interface.connect(addr)
            self.__dev_args.update({"name": addr, "sock": ret})
            self.__dev_args.update({"_length": self.__parser._threshold})
            self.dev = self.__dev_sock(self.__dev_args)
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
        update channel information, valid only when device is not acquiring data or impedance.

        Args:
            channels: channel number and name mapping, e.g. {0: "FPz", 1: "Oz", 2: "CPz"},
                if `None` is given, reset to all available channels with default names.

        Raises:
            Exception: if data/impedance acquisition in progress.
        """
        if self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            raise Exception(
                "Device acquisition in progress, please `stop_acquisition` first."
            )
        if channels is None:
            from .default_config import getChannels

            channels = getChannels(self.__dev_args["channel"])
        self.__dev_args.update({"ch_info": channels})
        ch_idx = [i for i in channels.keys()]
        self.__parser.update_chs(ch_idx)

    def start_acquisition_data(self):
        """
        Send data acquisition command to device, block until data acquisition started or failed.

        Raises:
            Exception: if device not connected or data acquisition init failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        if self.__status == iRecorder.Dev.SIGNAL:
            return None
        if self.__status == iRecorder.Dev.IMPEDANCE:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.SIGNAL_START
        while self.__status not in [iRecorder.Dev.SIGNAL, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.SIGNAL:
            self.__raise_sock_error()
        return None

    def get_data(self, timeout: Optional[float] = 0.02) -> list[Optional[list]]:
        """
        Acquire amplifier data, make sure this function is called in a loop so that it can continuously read the data.

        Args:
            timeout: Non-negative value, blocks at most `timeout` seconds and return, if set to `None`, blocks until new data is available.

        Returns:
            A list of frames, each frame is a list contains all wanted eeg channels and triggerbox channel,
                eeg channels can be updatd by `update_channels()`.

        Data Unit:
            - eeg: microvolts (µV)
            - triggerbox: int, from `0` to `255`

        Raises:
            Exception: if device not connected or in data acquisition mode.
        """
        if self.__socket_flag:
            self.__raise_sock_error()
        if self.__status != iRecorder.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        try:
            data: list = self.__save_data.get(timeout=timeout)
        except queue.Empty:
            return []
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def stop_acquisition(self) -> None:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.

        Raises:
            Exception: if device not connected or acquisition stop failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        self.__status = iRecorder.Dev.IDLE_START
        while self.__status not in [iRecorder.Dev.IDLE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.IDLE:
            self.__raise_sock_error()
        return None

    def start_acquisition_impedance(self) -> None:
        """
        Send impedance acquisition command to device, block until data acquisition started or failed.

        Raises:
            Exception: if device not connected or impedance acquisition init failed.
        """
        if self.__status == iRecorder.Dev.TERMINATE:
            self.__raise_sock_error()
        if self.__status == iRecorder.Dev.IMPEDANCE:
            return None
        if self.__status == iRecorder.Dev.SIGNAL:
            self.stop_acquisition()
        self.__status = iRecorder.Dev.IMPEDANCE_START
        while self.__status not in [iRecorder.Dev.IMPEDANCE, iRecorder.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iRecorder.Dev.IMPEDANCE:
            self.__raise_sock_error()
        return None

    def get_impedance(self) -> Optional[list]:
        """
        Acquire channel impedances, return immediatly, impedance update interval is about 2000ms.

        Returns:
            A list of channel impedance ranging from `0` to `np.inf` if available, otherwise `None`.

        Data Unit:
            - impedance: ohm (Ω)
        """
        if self.__socket_flag:
            if self.is_alive():
                self.close_dev()
            self.__raise_sock_error()
        return self.__parser.impedance

    def close_dev(self) -> None:
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
            importError: if `pylsl` is not installed or liblsl not installed for unix like system.
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
        Close LSL stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_flag = False
        if hasattr(self, "_lsl_stream"):
            del self._lsl_stream

    def save_bdf_file(self, filename: str):
        """
        Save data to BDF file, can be invoked after `start_acquisition_data()`.

        Args:
            filename: file name to save data, accept absolute or relative path.

        Raises:
            Exception: if data acquisition not started or `save_bdf_file` is invoked and BDF file already created.
            OSError: if BDF file creation failed, this may be caused by invalid file path or permission issue.
            importError: if `pyedflib` is not installed.
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
            f"iRecorder_{self.__dev_args['type']}_{self.__dev_args['name']}",
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
        Send marker to BDF file, can be invoked after `open_bdf_file()`, otherwise it will be ignored.

        Args:
            marker: marker string to write.
        """
        if hasattr(self, "_bdf_file"):
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
                if not data:
                    raise Exception("Remote transmission closed.")
                ret = self.__parser.parse_data(data)
                if ret:
                    self.__save_data.put(ret)
                    if self.__bdf_flag:
                        self._bdf_file.write_chunk(ret)
                    if self.__lsl_flag:
                        self._lsl_stream.push_chunk(ret)
            except Exception:
                if (self.__dev_args["type"] == "W32") and (retry < 1):
                    try:
                        print("Wi-Fi reconnecting...")
                        time.sleep(1)
                        self.dev.close_socket()
                        self.dev = self.__dev_sock(self.__dev_args, retry_timeout=3)
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
        print(f"Data thread closed. {datetime.now()}")

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
                # traceback.print_exc()
                self.__socket_flag = 5
                self.__status = iRecorder.Dev.TERMINATE_START

    def __get_chs(self) -> int:
        return int("".join([i for i in self.__dev_args["type"] if i.isdigit()]))

    def __finish_search(self):
        if self.__interface.is_alive():
            self.__interface.stop()
            self.__interface.join()
