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


class eConAlpha(Thread):
    class Dev(Enum):
        SIGNAL = 10
        SIGNAL_START = 11
        IDLE = 30
        IDLE_START = 31
        TERMINATE = 40
        TERMINATE_START = 41

    dev_args = {
        "type": "eConAlpha",
        "fs_emg": 500,
        "fs_imu": 62.5,
        "channel_emg": {
            0: "CH0",
            1: "CH1",
            2: "CH2",
            3: "CH3",
            4: "CH4",
            5: "CH5",
            6: "CH6",
            7: "CH7",
        },
        "channel_imu": {
            0: "ACC_X",
            1: "ACC_Y",
            2: "ACC_Z",
            3: "GRY_X",
            4: "GRY_Y",
            5: "GRY_Z",
        },
        "AdapterInfo": "Serial Port",
    }

    def __init__(self, port: Optional[str] = None) -> None:
        """
        Args:
            port: if not given, connect to the first available device.
        """
        super().__init__(daemon=True)
        self.__status = eConAlpha.Dev.TERMINATE
        if port is None:
            port = eConAlpha.find_devs()[0]
        self.__save_data = Queue()
        self.__parser = Parser()
        self.dev_args = deepcopy(eConAlpha.dev_args)
        self.dev = sock(port, self.__parser.threshold)
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
        self.__status = eConAlpha.Dev.IDLE_START
        self.__socket_flag = None
        self.__lsl_imu_flag = False
        self.__lsl_emg_flag = False
        self._bdf_file = None
        self.__enable_imu = False
        self.dev_args["name"] = port
        self.start()

    def set_frequency(self, fs_emg: Optional[int] = None):
        """
        Change the sampling frequency of iFocus.

        Args:
            fs_emg: sampling frequency of eeg data, should be 250, 500, 1000 or 2000.
                fs_imu will be automatically set to 1/8 of fs_emg.

        Raises:
            ValueError: if fs_emg is not valid.
            NotImplementedError: device firmware too old, not supporting 500Hz.
        """
        if self.__status == eConAlpha.Dev.SIGNAL:
            raise Exception("Data acquisition already started, please stop first.")
        if fs_emg is None:
            fs_emg = self.dev_args["fs_emg"]
        if fs_emg not in [250, 500, 1000, 2000]:
            raise ValueError("fs_emg should be 250 or 500")
        self.dev_args["fs_emg"] = fs_emg
        fs_imu = fs_emg / 8
        self.dev_args["fs_imu"] = fs_imu
        if hasattr(self, "dev"):
            self.dev.set_frequency(fs_emg)

    def get_dev_info(self) -> dict:
        """
        Get current device information, including device name, hardware channel number, acquired channels, sample frequency, etc.

        Returns:
            A dictionary containing device information, which includes:
                `type`: hardware type;
                `channel_emg`: channel dictionary, including EEG channel index and name;
                `channel_imu`: channel dictionary, including IMU channel index and name;
                `AdapterInfo`: adapter used for connection;
                `fs_emg`: sample frequency of EEG in Hz;
                `fs_imu`: sample frequency of IMU in Hz;
        """
        return deepcopy(self.dev_args)

    @staticmethod
    def find_devs() -> list:
        """
        Find available iFocus devices.

        Returns:
            available device ports.

        Raises:
            Exception: if no iFocus device found.
        """
        return sock.find_devs()

    def get_data(
        self, timeout: Optional[float] = 0.02
    ) -> Optional[list[Optional[list]]]:
        """
        Acquire all available data, make sure this function is called in a loop when `with_q` is set to `True` in`start_acquisition_data()`

        Args:
            timeout: Non-negative value, blocks at most 'timeout' seconds and return, if set to `None`, blocks until new data available.

        Returns:
            A list of frames, each frame is made up of 5 eeg data and 1 imu data in a shape as below:
                [[`emg_ch0_0,...,emg_ch8_0`],..., [`emg_ch0_7,...,emg_ch8_7`], [`acc_x`, `acc_y`, `acc_z`,`gry_x`,`gry_y`,`gry_z`]],
                    in which number `0~4` after `_` indicates the time order of channel data.

        Raises:
            Exception: if device not connected, connection failed, data transmission timeout/init failed, or unknown error.

        Data Unit:
            - eeg: µV
            - acc: mg
            - gry: bps
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
                if False, new data will not be directly available and can only be accessed through lsl stream.

        """
        self.__check_dev_status()
        self.__with_q = with_q
        if self.__status == eConAlpha.Dev.SIGNAL:
            return
        self.__status = eConAlpha.Dev.SIGNAL_START
        while self.__status not in [eConAlpha.Dev.SIGNAL, eConAlpha.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def stop_acquisition(self) -> None:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.
        """
        self.__check_dev_status()
        self.__status = eConAlpha.Dev.IDLE_START
        while self.__status not in [eConAlpha.Dev.IDLE, eConAlpha.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def open_lsl_emg(self):
        """
        Open LSL EMG stream, can be invoked after `start_acquisition_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            importError: if `pylsl` is not installed or liblsl not installed for unix like system.
        """
        if self.__status != eConAlpha.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, "_lsl_eeg"):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        self._lsl_emg = lslSender(
            self.dev_args["channel_emg"],
            f"{self.dev_args['type']}EMG{self.dev_args['name'][-2:]}",
            "EMG",
            self.dev_args["fs_emg"],
            with_trigger=False,
        )
        self.__lsl_emg_flag = True

    def close_lsl_eeg(self):
        """
        Close LSL EMG stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_emg_flag = False
        if hasattr(self, "_lsl_eeg"):
            del self._lsl_emg

    def open_lsl_imu(self):
        """
        Open LSL IMU stream, can be invoked after `start_acquisition_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            importError: if `pylsl` is not installed or liblsl not installed for unix like system.
        """
        if self.__status != eConAlpha.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, "_lsl_imu"):
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
        if hasattr(self, "_lsl_imu"):
            del self._lsl_imu

    def open_lsl_emg_imu(self):
        """
        Open LSL EMG and IMU stream, can be invoked after `start_acquisition_data()`.

        Raises:
            Exception: if data acquisition not started or LSL stream already opened.
            LSLException: if LSL stream creation failed.
            importError: if `pylsl` is not installed or liblsl not installed for unix like system.
        """
        if self.__status != eConAlpha.Dev.SIGNAL:
            raise Exception("Data acquisition not started, please start first.")
        if hasattr(self, "_lsl_emg_imu"):
            raise Exception("LSL stream already opened.")
        from ..utils.lslWrapper import lslSender

        key = 0
        elctds = {}
        for k, v in self.dev_args["channel_emg"].items():
            elctds[key] = v
            key += 1
        for k, v in self.dev_args["channel_imu"].items():
            elctds[key] = v
            key += 1
        self._lsl_emg_imu = lslSender(
            elctds,
            f"{self.dev_args['type']}EEG-IMU{self.dev_args['name'][-2:]}",
            "EEG-IMU",
            self.dev_args["fs_emg"] + self.dev_args["fs_imu"],
            unit="degree",
            with_trigger=False,
        )
        self.__lsl_emg_flag = True
        self.__lsl_imu_flag = True

    def close_lsl_emg_imu(self):
        """
        Close LSL EMG and IMU stream manually, invoked automatically after `stop_acquisition()` and `close_dev()`
        """
        self.__lsl_emg_flag = False
        self.__lsl_imu_flag = False
        if hasattr(self, "_lsl_emg_imu"):
            del self._lsl_emg_imu

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
        if self.__status != eConAlpha.Dev.SIGNAL:
            raise Exception("Data acquisition not started")
        if self._bdf_file is not None:
            raise Exception("BDF file already created.")
        from ..utils.bdfWrapper import bdfSaverEMG, bdfSaverEMGIMU

        if filename[-4:].lower() != ".bdf":
            filename += ".bdf"
        if self.__enable_imu:
            self._bdf_file = bdfSaverEMGIMU(
                filename,
                self.dev_args["channel_emg"],
                self.dev_args["fs_emg"],
                self.dev_args["channel_imu"],
                self.dev_args["fs_imu"],
                self.dev_args["type"],
            )
        else:
            self._bdf_file = bdfSaverEMG(
                filename,
                self.dev_args["channel_emg"],
                self.dev_args["fs_emg"],
                self.dev_args["type"],
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
        if hasattr(self, "_bdf_file"):
            self._bdf_file.write_Annotation(marker)

    def shock_band(self):
        """
        Send an instruction to shock the arm band
        """
        self.dev.shock_band()

    def close_dev(self):
        """
        Close device connection and release resources.
        """
        if self.__status != eConAlpha.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = eConAlpha.Dev.TERMINATE_START
            while self.__status != eConAlpha.Dev.TERMINATE:
                time.sleep(0.1)
        if self.is_alive():
            self.join()

    def __recv_data(self):
        try:
            self.dev.start_data()
            self.__status = eConAlpha.Dev.SIGNAL
        except Exception:
            self.__socket_flag = "SIGNAL mode initialization failed."
            self.__status = eConAlpha.Dev.TERMINATE_START

        while self.__status in [eConAlpha.Dev.SIGNAL]:
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
                    if self.__lsl_emg_flag and not self.__lsl_imu_flag:
                        self._lsl_emg.push_chunk(
                            [frame for frames in ret for frame in frames[:-1]]
                        )
                    elif self.__lsl_imu_flag and not self.__lsl_emg_flag:
                        self._lsl_imu.push_chunk([frame[-1] for frame in ret])
                    elif self.__lsl_emg_flag and self.__lsl_imu_flag:
                        self._lsl_emg_imu.push_chunk(
                            [frame for frames in ret for frame in frames[:-1]]
                            + [frame[-1] for frame in ret]
                        )
            except Exception as e:
                print(e)
                self.__socket_flag = "Data transmission timeout."
                self.__status = eConAlpha.Dev.TERMINATE_START

        # clear buffer
        self.close_lsl_eeg()
        self.close_lsl_imu()
        self.close_lsl_emg_imu()
        self.close_bdf_file()
        # self.dev.stop_recv()
        self.__parser.clear_buffer()
        self.__save_data.put(None)
        while self.__save_data.get() is not None:
            continue
        # stop recv data
        if self.__status != eConAlpha.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception:
                if self.__status == eConAlpha.Dev.IDLE_START:
                    self.__socket_flag = "Connection lost."
                self.__status = eConAlpha.Dev.TERMINATE_START

    def run(self):
        while self.__status != eConAlpha.Dev.TERMINATE_START:
            if self.__status == eConAlpha.Dev.SIGNAL_START:
                self.__recv_data()
            elif self.__status == eConAlpha.Dev.IDLE_START:
                self.__status = eConAlpha.Dev.IDLE
                while self.__status == eConAlpha.Dev.IDLE:
                    time.sleep(0.1)
            else:
                self.__socket_flag = f"Unknown status: {self.__status.name}"
                break
        try:
            self.dev.close_socket()
        finally:
            self.__status = eConAlpha.Dev.TERMINATE

    def __check_dev_status(self):
        if self.__socket_flag is None:
            return
        if self.is_alive():
            self.close_dev()
        raise Exception(str(self.__socket_flag))
