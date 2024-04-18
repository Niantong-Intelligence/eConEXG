from serial.tools.list_ports import comports
from queue import Queue
from threading import Thread

import time
class com(Thread):
    def __init__(self, device_queue: Queue , duration=3):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.duration = duration
        self.__search_flag = True

    def run(self):
        added_devices = set()
        start=time.time()
        while self.__search_flag:
            nearby_devices = comports()
            for device in nearby_devices:
                if not (device.pid == 0x5740 and device.vid == 0x0483):
                    continue
                name = device.device
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([ f"iRe-{device.serial_number}",name, name])
            time.sleep(0.5)
            if self.duration is None:
                continue
            if time.time()-start>self.duration:
                break

    def connect(self, port):
        self.__search_flag = False
        return port
