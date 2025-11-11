import time
import queue
from queue import Queue
from threading import Thread
from typing import Optional
from enum import Enum
from .data_parser import Parser
from .device_socket import sock
import traceback
from copy import deepcopy


class DFocus(Thread):
    class Dev(Enum):
        SIGNAL = 10
        SIGNAL_START = 11
        IDLE = 30
        IDLE_START = 31
        TERMINATE = 40
        TERMINATE_START = 41

    dev_args = {
        "type": "DFocus",
        "fs_exg": 250,
        "fs_imu": 50,
        "channel_exg": {0: "CH0", 1: "CH1"},
        "channel_imu": {0: "X", 1: "Y", 2: "Z"},
        "AdapterInfo": "Serial Port",
        "samples_per_packet": 5,  # Number of samples per electrode to be sent in one packet
    }

    def __init__(self, port: Optional[str] = None) -> None:
        """
        Args:
            port: if not given, connect to the first available device.
        """
        super().__init__(daemon=True)
        self.__status = DFocus.Dev.TERMINATE
        if port is None:
            port = DFocus.find_devs()[0]
        self.__save_data = Queue()
        self.__parser = Parser()
        self.dev_args = deepcopy(DFocus.dev_args)
        self.dev = sock(port)
        self.set_frequency()
        self.__with_q = True
        self.__socket_flag = "Device not connected, please connect first."
        self.__bdf_flag = False
        try:
            self.dev.connect_socket()
        except Exception as e:
            try:
                self.dev.close_socket()
            finally:
                raise e
        self.__status = DFocus.Dev.IDLE_START
        self.__socket_flag = None
        self.__lsl_imu_flag = False
        self.__lsl_exg_flag = False
        self.__enable_imu = False
        self.dev_args["name"] = port
        self.start()

    def set_frequency(self, fs_exg: int = None):
        """
        Change the sampling frequency of DFocus.

        Args:
            fs_exg: sampling frequency of exg data, should be 250 or 500,
                fs_imu will be automatically set to 1/5 of fs_exg.

        Raises:
            ValueError: if fs_exg is not 250 or 500.
            NotImplementedError: device firmware too old, not supporting 500Hz.
        """
        if self.__status == DFocus.Dev.SIGNAL:
            raise Exception("Data acquisition already started, please stop first.")
        if fs_exg is None:
            fs_exg = self.dev_args["fs_exg"]
        if fs_exg not in [250, 500, 1000]:
            raise ValueError("fs_exg should be 250, 500 or 1000")
        self.dev_args["fs_exg"] = fs_exg
        fs_imu = fs_exg // 5
        self.dev_args["fs_imu"] = fs_imu
        if hasattr(self, "dev"):
            self.dev.set_frequency(fs_exg)

    def get_dev_info(self) -> dict:
        """
        Get current device information, including device name, hardware channel number, acquired channels, sample frequency, etc.

        Returns:
            A dictionary containing device information, which includes:
                `type`: hardware type;
                `channel_exg`: channel dictionary, including EXG channel index and name;
                `channel_imu`: channel dictionary, including IMU channel index and name;
                `AdapterInfo`: adapter used for connection;
                `fs_exg`: sample frequency of EXG in Hz;
                `fs_imu`: sample frequency of IMU in Hz;
        """
        return deepcopy(self.dev_args)

    @staticmethod
    def find_devs() -> list:
        """
        Find available DFocus devices.

        Returns:
            available device ports.

        Raises:
            Exception: if no DFocus device found.
        """
        return sock._find_devs()

    def get_data(
        self, timeout: Optional[float] = 0.02
    ) -> Optional[list[Optional[list]]]:
        """
        Acquire all available data, make sure this function is called in a loop when `with_q` is set to `True` in`start_acquisition_data()`

        Args:
            timeout: Non-negative value, blocks at most 'timeout' seconds and return, if set to `None`, blocks until new data available.

        Returns:
            A list of frames, each frame is made up of 5 exg data and 1 imu data in a shape as below:
                [[`CH0_0`], [`CH0_1`], [`CH0_2`], [`CH0_3`], [`CH0_4`], [`CH0_0`], [`CH1_1`], [`CH1_2`], [`CH1_3`], [`CH1_4`], [`imu_x`, `imu_y`, `imu_z`]],
                    in which number `0~4` after `_` indicates the time order of channel data.

        Raises:
            Exception: if device not connected, connection failed, data transmission timeout/init failed, or unknown error.

        Data Unit:
            - exg: µV
            - imu: degree(°)
        """
        self.__check_dev_status()
        if not self.__with_q:
            return
        try:
            data: list = self.__save_data.get(timeout=timeout)
        except queue.Empty:
            return []
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def start_acquisition_data(self, with_q: bool = True) -> None:
        """
        Send data acquisition command to device, block until data acquisition started or failed.

        Args:
            with_q: if True, signal data will be stored in a queue and **should** be acquired by calling `get_data()` in a loop in case data queue is full.
                if False, new data will not be directly available and can only be acquired through lsl stream.

        """
        self.__check_dev_status()
        self.__with_q = with_q
        if self.__status == DFocus.Dev.SIGNAL:
            return
        self.__status = DFocus.Dev.SIGNAL_START
        while self.__status not in [DFocus.Dev.SIGNAL, DFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def stop_acquisition(self) -> None:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.
        """
        self.__check_dev_status()
        self.__status = DFocus.Dev.IDLE_START
        while self.__status not in [DFocus.Dev.IDLE, DFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def open_lsl_exg(self):
        """
        Open LSL EXG stream, can be invoked after `start_acquisition_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            ImportError: if `pylsl` is not installed or liblsl not installed for unix like system.
        """
        if self.__status != DFocus.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, '_lsl_exg'):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        self._lsl_exg = lslSender(
            self.dev_args["channel_exg"],
            f"{self.dev_args['type']}EXG{self.dev_args['name'][-2:]}",
            "EXG",
            self.dev_args["fs_exg"],
            with_trigger=False,
        )
        self.__lsl_exg_flag = True

    def close_lsl_exg(self):
        """
        Close LSL EXG stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_exg_flag = False
        if hasattr(self, '_lsl_exg'):
            del self._lsl_exg

    def open_lsl_imu(self):
        """
        Open LSL IMU stream, can be invoked after `start_acquisition_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            importError: if `pylsl` is not installed or liblsl not installed for unix like system.
        """
        if self.__status != DFocus.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, '_lsl_imu'):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        self._lsl_imu = lslSender(
            self.dev_args["channel_imu"],
            f"{self.dev_args['type']}IMU{self.dev_args['name'][-2:]}",
            "IMU",
            self.dev_args["fs_imu"],
            unit="degree",
            with_trigger=False,
        )
        self.__lsl_imu_flag = True

    def close_lsl_imu(self):
        """
        Close LSL IMU stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_imu_flag = False
        if hasattr(self, '_lsl_imu'):
            del self._lsl_imu

    def setIMUFlag(self, check):
        self.__enable_imu = check

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
        if self.__status != DFocus.Dev.SIGNAL:
            raise Exception("Data acquisition not started")
        if hasattr(self, '_bdf_file'):
            raise Exception("BDF file already created.")
        from ..utils.bdfWrapper import bdfSaverEXG, bdfSaverEXGIMU

        if filename[-4:].lower() != ".bdf":
            filename += ".bdf"
        if self.__enable_imu:
            self._bdf_file = bdfSaverEXGIMU(
                filename,
                self.dev_args["channel_exg"],
                self.dev_args["fs_exg"],
                self.dev_args["channel_imu"],
                self.dev_args["fs_imu"],
                self.dev_args["type"],
            )
        else:
            self._bdf_file = bdfSaverEXG(
                filename,
                self.dev_args["channel_exg"],
                self.dev_args["fs_exg"],
                self.dev_args["type"],
            )
        self.__bdf_flag = True

    def close_bdf_file(self):
        """
        Close and save BDF file manually, invoked automatically after `stop_acquisition()` or `close_dev()`
        """
        self.__bdf_flag = False
        if hasattr(self, '_bdf_file'):
            self._bdf_file.close_bdf()
            del self._bdf_file

    def send_bdf_marker(self, marker: str):
        """
        Send marker to BDF file, can be invoked after `create_bdf_file()`, otherwise it will be ignored.

        Args:
            marker: marker string to write.
        """
        if hasattr(self, "_bdf_file"):
            self._bdf_file.write_Annotation(marker)

    def close_dev(self):
        """
        Close device connection and release resources.
        """
        if self.__status != DFocus.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = DFocus.Dev.TERMINATE_START
            while self.__status != DFocus.Dev.TERMINATE:
                time.sleep(0.1)
        if self.is_alive():
            self.join()

    def __recv_data(self):
        try:
            self.dev.start_data()
            self.__status = DFocus.Dev.SIGNAL
        except Exception:
            self.__socket_flag = "SIGNAL mode initialization failed."
            self.__status = DFocus.Dev.TERMINATE_START

        while self.__status in [DFocus.Dev.SIGNAL]:
            try:
                data = self.dev.recv_socket()
                if not data:
                    raise Exception("Data transmission timeout.")
                ret = self.__parser.parse_data(data)
                if ret:
                    if self.__with_q:
                        self.__save_data.put(ret)
                    if self.__bdf_flag:
                        self._bdf_file.write_chunk(ret)
                    if self.__lsl_exg_flag:
                        self._lsl_exg.push_chunk(
                            [frame for frames in ret for frame in frames[:-1]]
                        )
                    if self.__lsl_imu_flag:
                        self._lsl_imu.push_chunk([frame[-1] for frame in ret])
            except Exception as e:
                print(e)
                self.__socket_flag = "Data transmission timeout."
                self.__status = DFocus.Dev.TERMINATE_START

        # clear buffer
        self.close_lsl_exg()
        self.close_lsl_imu()
        self.close_bdf_file()
        # self.dev.stop_recv()
        self.__parser.clear_buffer()
        self.__save_data.put(None)
        while self.__save_data.get() is not None:
            continue
        # stop recv data
        if self.__status != DFocus.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception:
                if self.__status == DFocus.Dev.IDLE_START:
                    self.__socket_flag = "Connection lost."
                self.__status = DFocus.Dev.TERMINATE_START

    def run(self):
        while self.__status != DFocus.Dev.TERMINATE_START:
            if self.__status == DFocus.Dev.SIGNAL_START:
                self.__recv_data()
            elif self.__status == DFocus.Dev.IDLE_START:
                self.__status = DFocus.Dev.IDLE
                while self.__status == DFocus.Dev.IDLE:
                    time.sleep(0.1)
            else:
                self.__socket_flag = f"Unknown status: {self.__status.name}"
                break
        try:
            self.dev.close_socket()
        finally:
            self.__status = DFocus.Dev.TERMINATE

    def __check_dev_status(self):
        if self.__socket_flag is None:
            return
        if self.is_alive():
            self.close_dev()
        raise Exception(str(self.__socket_flag))
