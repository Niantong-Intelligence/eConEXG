from .. import bluetooth
from queue import Queue
from threading import Thread


class conn(Thread):
    def __init__(self, device_queue: Queue, device_config):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__device_config = device_config
        self.__search_flag = True

    def run(self):
        added_devices = set()
        search_interval = 0
        try:
            self.device_queue.put([str(bluetooth.read_local_bdaddr())])
        except Exception:
            warn = "Bluetooth card disabled or not inserted, please enable it in system setting."
            self.device_queue.put(warn)
            return
        while self.__search_flag:
            search_interval = min(search_interval + 1, 3)
            nearby_devices = bluetooth.discover_devices(
                lookup_names=True, duration=search_interval
            )
            for device in nearby_devices:
                addr = device[0]
                name = device[1]
                if self.__device_config["channel"] == 16:
                    if "iRecorder-" not in name:
                        continue
                elif self.__device_config["channel"] == 8:
                    if "iRecorder8-" not in name:
                        continue
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([addr, name, "1"])

    def stop(self):
        self.__search_flag = False

    def connect(self, addr):
        self.__search_flag = False
        if addr == "":
            return None
        uuid = "00001101-0000-1000-8000-00805f9b34fb"
        service_matches = bluetooth.find_service(uuid=uuid, address=addr)
        if len(service_matches) == 0:
            warn = "Bluetooth connection failed, please retry."
            self.device_queue.put(warn)
            return None
        device = service_matches[0]
        print("bluetooth connected!")
        return (device["host"],device["port"])
