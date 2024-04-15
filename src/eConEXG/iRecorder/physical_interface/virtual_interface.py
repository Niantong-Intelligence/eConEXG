import time
from queue import Queue
from threading import Thread

class conn(Thread):
    def __init__(self, device_queue: Queue, device_config):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__device_config = device_config

    def run(self):
        time.sleep(0.1)
        self.device_queue.put(['virtual dev', 'iRecorder-virtual', "1"])

    def stop(self):
        pass

    def connect(self, ssid):
        if ssid == "":
            return False
        return True
