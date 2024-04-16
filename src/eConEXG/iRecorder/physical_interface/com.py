from serial.tools.list_ports import comports
from queue import Queue
from threading import Thread


class conn(Thread):
    def __init__(self, device_queue: Queue, device_config):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__search_flag = True

    def run(self):
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            search_interval = min(search_interval + 1, 5)
            nearby_devices = comports()
            for device in nearby_devices:
                if not (device.pid == 0x5740 and device.vid == 0x0483):
                    continue
                name = device.device
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([ f"iRe-{device.serial_number}",name, name])

    def stop(self):
        self.__search_flag = False

    def connect(self, port):
        self.__search_flag = False
        if port == "":
            return False
        return port
