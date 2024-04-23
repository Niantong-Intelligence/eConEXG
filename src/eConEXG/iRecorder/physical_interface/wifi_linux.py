import time
from queue import Queue
from threading import Thread
import netifaces
import subprocess


class wifiLinux(Thread):
    cmd_search = ["nmcli", "device", "wifi", "list", "ifname"]
    cmd_con = ["nmcli", "device", "wifi", "connect"]

    def __init__(self, device_queue: Queue):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.port = 4321
        self.__search_flag = True
        self.__interface = self.validate_interface()
        self.__connected = ""

    @property
    def interface(self):
        return self.__interface

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
            line.split()[0] for line in output_lines if "wifi" in line.lower().split()
        ]
        if not len(wifi_interfaces):
            raise Exception(
                "Wi-Fi interface not found, please insert a USB interface card."
            )
        self.__interface = wifi_interfaces[0]
        result = subprocess.run(
            self.cmd_search + [self.__interface, "--rescan", "no"],
            capture_output=True,
            text=True,
        )
        output_lines = result.stdout.split("\n")
        if len(output_lines) <= 2:
            raise Exception(
                "Wi-Fi interface disabled, please enable it in system setting."
            )

        # for interface in wifi.interfaces():
        #     if any(sub in interface.name() for sub in ["USB", "usb"]):
        #         break

        return self.__interface

    def run(self):
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            dur = time.time()
            result = subprocess.run(
                self.cmd_search + [self.__interface, "--rescan", "yes"],
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

        retry = 0
        while retry <= 1:
            result = subprocess.run(
                self.cmd_con + [ssid, "ifname", self.__interface],
                capture_output=True,
                text=True,
            )
            output = result.stdout
            if "successfully" in output:
                time.sleep(2)
                host = self._get_default_gateway()
                if host is not None:
                    return (host, self.port)
            elif retry <= 1:
                subprocess.run(
                    self.cmd_search + [self.__interface, "--rescan", "yes"],
                    capture_output=True,
                    text=True,
                )
                retry += 1

        warn = "Wi-Fi connection failed, please retry.\nFor encrypted device, connect through system wifi setting first."
        raise Exception(warn)
