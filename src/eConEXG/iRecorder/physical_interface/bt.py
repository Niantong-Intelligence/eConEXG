from queue import Queue
from threading import Thread

from . import bluetooth

CHANNELS = {"W8": False, "W16": False}


class bt(Thread):
    def __init__(self, device_queue: Queue):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__search_flag = True
        self.__interface = self.validate_interface()

    @property
    def interface(self):
        return self.__interface

    def validate_interface(self):
        try:
            return str(bluetooth.read_local_bdaddr())
        except Exception:
            warn = "Bluetooth card disabled or not inserted, please enable it in system setting."
            raise Exception(warn)

    def run(self):
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            search_interval = min(search_interval + 1, 3)
            nearby_devices = bluetooth.discover_devices(
                lookup_names=True, duration=search_interval
            )
            for device in nearby_devices:
                addr = device[0]
                name = device[1]
                if "iRecorder-" not in name:
                    if not CHANNELS["W16"]:
                        continue
                if "iRecorder8-" not in name:
                    if not CHANNELS["W8"]:
                        continue
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([name, addr, addr])

    def stop(self):
        self.__search_flag = False

    def connect(self, addr):
        self.stop()
        uuid = "00001101-0000-1000-8000-00805f9b34fb"
        service_matches = bluetooth.find_service(uuid=uuid, address=addr)
        if len(service_matches) == 0:
            warn = "Bluetooth connection failed, please retry."
            raise Exception(warn)
        device = service_matches[0]
        return (device["host"], device["port"])
