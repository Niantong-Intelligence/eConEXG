import time
from queue import Queue
from threading import Thread
from serial.tools.list_ports import comports
from typing import Literal


class com(Thread):
    def __init__(
        self, dev_type: Literal["USB8", "USB16", "USB32"], device_queue: Queue
    ):
        super().__init__(daemon=True)
        self.dev_type = dev_type
        self.device_queue = device_queue
        self.__search_flag = True
        self.added_devices = {}

    @property
    def interface(self):
        return "Serial Port"

    def __find_devices(self):
        nearby_devices = comports()
        for device in nearby_devices:
            if not (device.pid == 0x5740 and device.vid == 0x0483):
                continue
            serial_number = device.serial_number.split("_")
            if self.dev_type == "USB8":
                if "ir1" != serial_number[0].lower():
                    continue
                display_name = f"iRe8-{serial_number[-1]}"
            elif self.dev_type == "USB16":
                if "ir2" != serial_number[0].lower():
                    continue
                display_name = f"iRe16-{serial_number[-1]}"
            elif self.dev_type == "USB32":
                if serial_number[0].lower() in ["ir1", "ir2"]:
                    continue
                display_name = f"iRe32-{serial_number[-1]}"
            else:
                return
            if display_name not in self.added_devices.keys():
                self.added_devices[display_name] = device.device
                self.device_queue.put([display_name, device.device, display_name])

    def run(self):
        while self.__search_flag:
            self.__find_devices()
            time.sleep(0.5)

    def stop(self):
        self.__search_flag = False

    def connect(self, port):
        self.stop()
        if not self.added_devices:
            self.__find_devices()
        if port in self.added_devices.keys():
            return self.added_devices[port]
        raise Exception("Invalid device name!")
