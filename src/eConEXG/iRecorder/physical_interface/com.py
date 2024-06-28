import time
from queue import Queue
from threading import Thread
from typing import Literal

from serial.tools.list_ports import comports

CHANNELS: Literal["USB8", "USB32"] = "USB32"


class com(Thread):
    def __init__(self, device_queue: Queue):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__search_flag = True

    @property
    def interface(self):
        return "COM"

    def run(self):
        added_devices = set()
        # platf = system()
        while self.__search_flag:
            nearby_devices = comports()
            for device in nearby_devices:
                if not (device.pid == 0x5740 and device.vid == 0x0483):
                    continue
                name = device.device
                # if platf in ["Windows", "Darwin"] else device.name
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([f"iRe-{device.serial_number}", name, name])
            time.sleep(0.5)

    def stop(self):
        self.__search_flag = False

    def connect(self, port):
        self.stop()
        return port
