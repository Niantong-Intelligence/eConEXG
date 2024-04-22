import time
from queue import Queue
from threading import Thread
import netifaces
import subprocess


class wifiLinux(Thread):
    cmd = ["nmcli", "device", "wifi", "list", "ifname"]

    def __init__(self, device_queue: Queue):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.port = 4321
        self.__search_flag = True
        self.__interface = None
        self.__connected = ""
        self.validate_interface()

    def validate_interface(self):
        # Run nmcli device command and capture the output
        result = subprocess.run(
            ["nmcli", "device"],
            capture_output=True,
            text=True,
        )

        # Split the output into lines
        output_lines = result.stdout.split("\n")

        # Filter out lines containing 'wifi'
        wifi_interfaces = [
            line.split()[0] for line in output_lines if "wifi" in line.lower()
        ]
        if not len(wifi_interfaces):
            raise Exception(
                "Wi-Fi interface not found, please insert a USB interface card."
            )
        self.__interface = wifi_interfaces[0]
        result = subprocess.run(
            self.cmd + [self.__interface, "--rescan", "no"],
            capture_output=True,
            text=True,
        )
        output_lines = result.stdout.split("\n")
        if len(output_lines) == 1:
            raise Exception(
                "Wi-Fi interface disabled, please enable it in system setting."
            )

        # for interface in wifi.interfaces():
        #     if any(sub in interface.name() for sub in ["USB", "usb"]):
        #         break

    def run(self):
        self.device_queue.put([str(self.__interface)])
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            dur = time.time()
            result = subprocess.run(
                self.cmd + [self.__interface, "--rescan", "yes"],
                capture_output=True,
                text=True,
            )
            search_interval = min(search_interval + 0.5, 5)
            while time.time() - dur < search_interval:
                if not self.__search_flag:
                    return
                time.sleep(0.5)
            output_lines = result.stdout.split("\n")
            for i in output_lines:
                components = i.split()
                if len(components) < 4:
                    continue
                bias = 1 if components[0] == "*" else 0
                name = components[1 + bias]
                if "iRe" not in name:
                    continue
                if bias == 1:
                    self.__connected = name
                if name not in added_devices:
                    added_devices.add(name)
                    self.device_queue.put([name, components[0 + bias], name])
    def _get_default_gateway(self):  # TODO: some problems under multiple interfaces
        gateways = netifaces.gateways()
        for ips in gateways[netifaces.AF_INET]:
            print(ips)
            if ips[1] == self.__interface:
                return ips[0]

    def stop(self):
        self.__search_flag = False

    def connect(self, ssid):
        self.stop()
        if self.__connected == ssid:  # return if connected
            host = self._get_default_gateway()
            if host is not None:
                return (host, self.port)
        self.__interface.disconnect()
        time.sleep(2)
        
        for i in range(5):
            self.__interface.connect(profile)
            time.sleep(0.5 * (i + 1))
            if self.__interface.status() == pywifi.const.IFACE_CONNECTED:
                time.sleep(1)
                host = self._get_default_gateway()
                if host is not None:
                    return (host, self.port)
                else:
                    break
            print("...Retry connecting:", i + 1)
        if any(sub in self.__interface.name() for sub in ["USB", "usb"]):
            self.__interface.remove_all_network_profiles()
            self.__interface.disconnect()
        warn = "Wi-Fi connection failed, please retry.\nFor encrypted device, connect through system wifi setting first."
        raise Exception(warn)
