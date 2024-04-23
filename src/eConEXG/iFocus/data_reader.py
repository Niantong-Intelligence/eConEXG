import time
import queue
from queue import Queue
from threading import Thread
from typing import Optional
from enum import Enum
from .eegParser import Parser
from .device_socket import sock
import traceback


class iFocus(Thread):
    class Dev(Enum):
        SIGNAL = 10
        SIGNAL_START = 11
        IDLE = 30
        IDLE_START = 31
        TERMINATE = 40
        TERMINATE_START = 41

    def __init__(self, port: Optional[str]):
        """
        Parameters
        ----------
        port: str | None
            if not given, connect to the first available device
        """
        super().__init__(daemon=True)
        if port is None:
            port = self.find_devs()
        self.__save_data = Queue()
        self.__parser = Parser()
        self.dev = sock(port)
        self.__socket_flag = 1
        try:
            self.dev.connect_socket()
        except Exception as e:
            try:
                self.dev.close_socket()
            finally:
                raise e
        self.__status = iFocus.Dev.IDLE_START
        self.__socket_flag = 0
        self.start()

    @staticmethod
    def find_devs():
        from serial.tools.list_ports import comports

        devices = comports()
        for device in devices:
            if "FTDI" in device.manufacturer:
                if device.serial_number in ["IFOCUSA", "iFocus"]:
                    return device.device
        raise Exception("iFocus device not found")

    def get_battery_value(self):
        """
        Query battery level.

        Returns
        -------
        battery level in percentage, range from `0` to `100`.
        """
        return self.__parser.bat

    def get_data(self, timeout: Optional[float] = None) -> Optional[list]:
        try:
            data: list = self.__save_data.get(block=timeout)
        except queue.Empty:
            return
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def start_acquisition_data(self) -> Optional[True]:
        """
        Send data acquisition command to device, block until data acquisition started or failed.
        """
        if self.__status == iFocus.Dev.TERMINATE:
            self.__raise_sock_error()
        if self.__status == iFocus.Dev.SIGNAL:
            return True
        self.__status = iFocus.Dev.SIGNAL_START
        while self.__status not in [iFocus.Dev.SIGNAL, iFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iFocus.Dev.SIGNAL:
            self.__raise_sock_error()

    def stop_acquisition(self) -> Optional[True]:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.
        """
        if self.__status == iFocus.Dev.TERMINATE:
            self.__raise_sock_error()
        self.__status = iFocus.Dev.IDLE_START
        while self.__status not in [iFocus.Dev.IDLE, iFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        if self.__status != iFocus.Dev.IDLE:
            self.__raise_sock_error()

    def close_dev(self):
        """
        Close device connection and release resources.
        """
        if self.__status != iFocus.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = iFocus.Dev.TERMINATE_START
            while self.__status != iFocus.Dev.TERMINATE:
                time.sleep(0.1)
        if self.is_alive():
            self.join()

    def __recv_data(self):
        try:
            self.dev.start_data()
            self.__status = iFocus.Dev.SIGNAL
        except Exception:
            print("SIGNAL START FAILED!")
            self.__socket_flag = 4
            self.__status = iFocus.Dev.TERMINATE_START

        print("SIGNAL START")
        while self.__status in [iFocus.Dev.SIGNAL]:
            try:
                data = self.dev.recv_socket()
                ret = self.__parser.parse_data(data)
                if ret:
                    self.__save_data.put(ret)
            except Exception:
                traceback.print_exc()
                self.__socket_flag = 3
                self.__status = iFocus.Dev.TERMINATE_START

        # clear buffer
        self.__parser.clear_buffer()
        self.__save_data.put(None)
        while self.__save_data.get() is not None:
            continue
        # stop recv data
        if self.__status != iFocus.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception:
                if self.__status == iFocus.Dev.IDLE_START:
                    self.__socket_flag = 5
                self.__status = iFocus.Dev.TERMINATE_START
        print("Data thread closed")

    def run(self):
        while self.__status != iFocus.Dev.TERMINATE_START:
            if self.__status == iFocus.Dev.SIGNAL_START:
                self.__recv_data()
            elif self.__status == iFocus.Dev.IDLE_START:
                self.dev.stop_recv()
                self.__status = iFocus.Dev.IDLE
                while self.__status == iFocus.Dev.IDLE:
                    time.sleep(0.1)
            else:
                print(f"Unknown status: {self.__status}")
                break
        try:
            self.dev.close_socket()
        except Exception:
            print("socket close failed")
        finally:
            self.__status = iFocus.Dev.TERMINATE
            print("iFocus disconnected")

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
