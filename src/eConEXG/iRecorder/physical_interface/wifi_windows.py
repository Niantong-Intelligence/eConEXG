import time
from queue import Queue
from threading import Thread
import netifaces
import pywifi
import subprocess
import locale
from traceback import print_exc


class conn(Thread):
    def __init__(self, device_queue: Queue, device_config):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.__device_config = device_config
        self.__device_config["port"] = 4321
        self.__search_flag = True
        self.__interface = None

    def run(self):
        wifi = pywifi.PyWiFi()
        interface = None
        for interface in wifi.interfaces():
            if any(sub in interface.name() for sub in ["USB", "usb"]):
                break
        if interface is None:
            warn = "Wi-Fi interface not found, please insert a USB interface card."
            self.device_queue.put(warn)
            return
        self.__interface = interface
        self.device_queue.put([str(self.__interface.name())])
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            self.__interface.scan()
            time.sleep(min(search_interval + 0.5, 5))
            try:
                devices = self.__interface.scan_results()
            except Exception:
                warn = "Wi-Fi interface disabled, please enable it in system setting."
                self.device_queue.put(warn)
                return
            for device in devices:
                if "iRe" not in device.ssid:
                    continue
                if device.ssid not in added_devices:
                    added_devices.add(device.ssid)
                    self.device_queue.put([device.ssid, device.bssid[:-1], "1"])
        print("search finished")

    def stop(self):
        self.__search_flag = False

    def _get_default_gateway(self):  # TODO: some problems under multiple interfaces
        gateways = netifaces.gateways()
        for ips in gateways[netifaces.AF_INET]:
            if ips[1] == str(self.__interface._raw_obj["guid"]):
                return ips[0]

    def _get_connected_wifi_name(self):
        iface = str(self.__interface._raw_obj["guid"])[1:-1]
        try:
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"], creationflags=0x08000000
            )
            output = output.decode(locale.getpreferredencoding())
            for profile in output.split("\r\n\r\n"):
                if (iface.lower() in profile) or (iface in profile):
                    lines = profile.split("\n")
                    for line in lines:
                        if "SSID" in line:
                            return line.split(":")[1].strip()
        except subprocess.CalledProcessError:
            print_exc()
            return None
        return None

    def connect(self, ssid):
        self.__search_flag = False
        if ssid == "":
            return False
        if self._get_connected_wifi_name() == ssid:  # return if connected
            self.__device_config["host"] = self._get_default_gateway()
            if self.__device_config["host"] is not None:
                return True
        self.__interface.disconnect()
        time.sleep(2)
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile = self.__interface.add_network_profile(profile)
        for i in range(5):
            self.__interface.connect(profile)
            time.sleep(0.5 * (i + 1))
            if self.__interface.status() == pywifi.const.IFACE_CONNECTED:
                time.sleep(1)
                self.__device_config["host"] = self._get_default_gateway()
                if self.__device_config["host"] is not None:
                    return True
                else:
                    break
            print("...Retry connecting:", i + 1)
        warn = "Wi-Fi connection failed, please retry.\nFor encrypted device, connect through system wifi setting first."
        self.device_queue.put(warn)
        if any(sub in self.__interface.name() for sub in ["USB", "usb"]):
            self.__interface.remove_all_network_profiles()
            self.__interface.disconnect()
        return False
