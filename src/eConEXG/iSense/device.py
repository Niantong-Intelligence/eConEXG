import queue
import time
import traceback
from datetime import datetime
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Optional


class iSense(Thread):
    class Dev(Enum):
        SIGNAL = 10  # self.Dev.SIGNAL transmision mode
        SIGNAL_START = 11
        IMPEDANCE = 20  # self.Dev.IMPEDANCE transmision mode
        IMPEDANCE_START = 21
        IDLE = 30  # self.Dev.IDLE mode
        IDLE_START = 31
        TERMINATE = 40  # Init state
        TERMINATE_START = 41

    def __init__(self, fs: int):
        from .data_parser import Parser
        from .dev_socket import iSenseUSB

        print("initing iSense")
        super().__init__(daemon=True)
        if fs not in {250, 500, 1000, 2000, 4000, 8000, 16000}:
            raise ValueError("Frequency is unsupported. Available frequencies: 250, 500, 1000, 2000, 4000, 8000, 16000")
        self.fs = fs
        self.__socket_flag = Queue()
        self.__save_data = Queue()
        self.__batt = 0
        self.__status = self.Dev.TERMINATE
        try:
            self.__parser = Parser(fs=self.fs)
            self.__dev = iSenseUSB(self.fs, self.__parser.pkt_size)
            self.__dev.connect_socket()
            self.__dev.stop_recv()
            self.__socket_flag.put("Connected")
            self.__status = self.Dev.IDLE_START
            self.start()
        except Exception as e:
            traceback.print_exc()
            self.__socket_flag.put(f"Error: {e}")
            return

    def start_acquisition_data(self) -> None:
        """
        Send data acquisition command to device, block until data acquisition started or failed.
        """
        if self.__status == self.Dev.TERMINATE:
            return  # TODO: add raise exception
        if self.__status == self.Dev.SIGNAL:
            return
        if self.__status == self.Dev.IMPEDANCE:
            self.stop_acquisition()
        self.__status = self.Dev.SIGNAL_START
        while self.__status not in [self.Dev.SIGNAL, self.Dev.TERMINATE]:
            time.sleep(0.01)

    def get_data(self, timeout: Optional[float] = 0.01) -> list[Optional[list]]:
        """
        Acquire amplifier data, make sure this function is called in a loop so that it can continuously read the data.

        Args:
            timeout: it blocks at most `timeout` seconds and return, otherwise it returns until new data is available.

        Returns:
            A list of frames, each frame is a list contains all wanted eeg channels and triggerbox channel,
                eeg channels can be updatd by `update_channels()`.

        Data Unit:
            - eeg: microvolts (µV)
            - triggerbox: int, from `0` to `255`

        Raises:
            Exception: if device not connected or in data acquisition mode.
        """
        # if self.__status != self.Dev.SIGNAL:
        #     raise Exception("Data acquisition not started, please start first.")
        try:
            data: list = self.__save_data.get(timeout=timeout)
        except queue.Empty:
            return []
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def stop_acquisition(self) -> None:
        """
        Stop data or self.Dev.IMPEDANCE acquisition, block until data acquisition stopped or failed.
        """
        if self.__status in [self.Dev.IDLE, self.Dev.TERMINATE]:
            return
        self.__status = self.Dev.IDLE_START
        while self.__status not in [self.Dev.IDLE, self.Dev.TERMINATE]:
            time.sleep(0.01)

    def start_acquisition_impedance(self) -> None:
        """
        Send self.Dev.IMPEDANCE acquisition command to device, block until data acquisition started or failed.
        """
        if self.__status == self.Dev.TERMINATE:
            return  # TODO: add raise exception
        if self.__status == self.Dev.IMPEDANCE:
            return None
        if self.__status == self.Dev.SIGNAL:
            self.stop_acquisition()
        self.__status = self.Dev.IMPEDANCE_START
        while self.__status not in [self.Dev.IMPEDANCE, self.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != self.Dev.IMPEDANCE:
            return  # TODO: add raise exception
        return None

    def get_impedance(self) -> Optional[list]:
        """
        Acquire channel impedances, return immediatly, self.Dev.IMPEDANCE update interval is about 2000ms.

        Returns:
            A list of channel self.Dev.IMPEDANCE ranging from `0` to `math.nan` if available, oterwise None.

        Data Unit:
            - self.Dev.IMPEDANCE: ohm (Ω)
        """
        return self.__parser.impedance

    def close_dev(self) -> None:
        """
        Close device connection and release resources.
        """
        if self.__status not in [self.Dev.TERMINATE]:
            # ensure socket is closed correctly
            self.__status = self.Dev.TERMINATE_START
            self.join()

    def get_battery_value(self) -> int:
        """
        Query battery level.

        Returns:
            battery level in percentage, range from `0` to `100`.
        """
        if (self.__parser.batt_val >= 0) and (self.__parser.batt_val <= 100):
            self.__batt = self.__parser.batt_val
        return self.__batt

    def get_dev_flag(self) -> Optional[str]:
        """
        Query device status

        Returns:
            A list of strings.
            Possible results: Connected, Connected lost, Error, Initialization failed...
        """
        try:
            return self.__socket_flag.get_nowait()
        except queue.Empty:
            return

    @staticmethod
    def get_available_frequency() -> list:
        """Get available sample frequencies of iSense.

        Returns:
            Available sample frequencies in Hz.
        """
        return [250, 500, 1000, 2000, 4000, 8000, 16000]

    def run(self):
        while self.__status not in [self.Dev.TERMINATE_START]:
            if self.__status == self.Dev.SIGNAL_START:
                self.__recv_data(imp_mode=False)
            elif self.__status == self.Dev.IMPEDANCE_START:
                self.__recv_data(imp_mode=True)
            elif self.__status in [self.Dev.IDLE_START]:
                self.__idle_state()
            else:
                print(f"Unknown status: {self.__status}")
                break
        try:
            self.__dev.close_socket()
        except Exception:
            pass
        self.__status = self.Dev.TERMINATE
        print("iSense disconnected")

    def __recv_data(self, imp_mode=True):
        self.__parser.imp_flag = imp_mode
        try:
            if self.__parser.imp_flag:
                self.__dev.start_impe()
                self.__status = self.Dev.IMPEDANCE
            else:
                self.__dev.start_data()
                self.__status = self.Dev.SIGNAL
        except Exception as e:
            self.__socket_flag.put(f"Data/IMPEDANCE initialization failed: {e}")
            self.__status = self.Dev.TERMINATE_START

        try:
            while self.__status in [self.Dev.SIGNAL, self.Dev.IMPEDANCE]:
                data = self.__dev.recv_socket()
                if not data:
                    raise Exception("Remote end closed.")
                ret = self.__parser.parse_data(data)
                if ret:
                    self.__save_data.put(ret)
        except Exception as e:
            traceback.print_exc()
            self.__socket_flag.put(f"Transmission error: {e}")
            self.__status = self.Dev.TERMINATE_START

        try:
            self.__dev.stop_recv()
        except Exception as e:
            if self.__status == self.Dev.IDLE_START:
                traceback.print_exc()
                self.__socket_flag.put(f"IDLE initialization failed: {e}")
            self.__status = self.Dev.TERMINATE_START

        self.__parser.clear_buffer()
        self.__save_data.put(None)
        while self.__save_data.get() is not None:
            continue
        print(f"iSense data thread closed. {datetime.now()}")

    def __idle_state(self):
        timestamp = time.time()
        self.__status = self.Dev.IDLE
        while self.__status in [self.Dev.IDLE]:
            if (time.time() - timestamp) < 10:
                time.sleep(0.2)  # to reduce cpu usage
                continue
            try:  # heartbeat to keep socket alive and update battery level
                self.__dev.stop_recv()
                timestamp = time.time()
                # print("Ah, ah, ah, ah\nStayin' alive, stayin' alive")
            except Exception:
                traceback.print_exc()
                self.__socket_flag.put("Connection Lost!")
                self.__status = self.Dev.TERMINATE_START
