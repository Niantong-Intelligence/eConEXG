from queue import Queue
from threading import Thread
import subprocess
import locale
import netifaces
import time

class conn(Thread):
    PATH_OF_AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

    def __init__(self, device_queue: Queue, device_config):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__device_config = device_config
        self.__device_config["port"] = 4321

    def _find_interface(self):
        out = subprocess.check_output(["networksetup", "-listallhardwareports"])
        interfaces = out.decode(locale.getpreferredencoding()).split("\n\n")
        for iface in interfaces:
            if "Wi-Fi" not in iface:
                continue
            lines = iface.split("\n")
            for line in lines:
                if "Device" not in line:
                    continue
                self.iface = line.split(":")[1].strip()
                self.device_queue.put([str(self.iface)])
                return
        raise Exception

    def _get_default_gateway(self):
        time.sleep(1)
        gateways = netifaces.gateways()
        for ips in gateways[netifaces.AF_INET]:
            if ips[1] == self.iface:
                self.__device_config["host"] = ips[0]

    def run(self):
        try:
            self._find_interface()
        except Exception:
            self.device_queue.put("Wi-Fi interface not found")
        added_devices = set()
        command = [self.PATH_OF_AIRPORT, "-s"]
        self.child_process = subprocess.Popen(command, stdout=subprocess.PIPE)
        result, _ = self.child_process.communicate()
        result = result.decode(locale.getpreferredencoding())
        output = result.splitlines()
        if not output:
            self.device_queue.put("Failed to scan WiFi devices.")
            return
        for line in output[1:]:
            fields = line.split()
            ssid = fields[0]  # 1:bssid, 2:rssi
            if "iRe" not in ssid:
                continue
            if ssid not in added_devices:
                added_devices.add(ssid)
                self.device_queue.put([ssid, "", "1"])

    def stop(self):
        if self.child_process.poll() is None:
            self.child_process.wait()

    def connect(self, ssid):
        self.stop()
        if not ssid:
            return False
        # check if network already connected
        command = ["networksetup", "-getairportnetwork", self.iface]
        result = subprocess.check_output(command)
        result = result.decode(locale.getpreferredencoding())
        if result.split(":")[1].strip() == ssid:
            self._get_default_gateway()
            return True
        # connect
        command = ["networksetup", "-setairportnetwork", self.iface, ssid]
        self.child_process = subprocess.Popen(command, stdout=subprocess.PIPE)
        out, _ = self.child_process.communicate()
        # process.wait()
        result = out.decode(locale.getpreferredencoding())
        if not result:
            self._get_default_gateway()
            return True
        else:
            self.device_queue.put(result)
            return False