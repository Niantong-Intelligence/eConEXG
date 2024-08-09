import time
from queue import Queue
from threading import Thread
import netifaces
import pywifi
import subprocess
import locale
from traceback import print_exc


class wifiWindows(Thread):
    def __init__(self, device_queue: Queue) -> str:
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.port = 4321
        self.__search_flag = True
        self.__iface = self.validate_interface()

    @property
    def interface(self):
        return str(self.__iface.name())

    def validate_interface(self):
        wifi = pywifi.PyWiFi()
        interface = None
        for interface in wifi.interfaces():
            if "usb" in interface.name().lower():
                break
        if interface is None:
            warn = "Wi-Fi interface not found, please insert a USB interface card."
            raise Exception(warn)
        try:
            interface.scan_results()
        except Exception:
            warn = "Wi-Fi interface disabled, please enable it in system setting."
            raise Exception(warn)
        return interface

    def run(self):
        added_devices = set()
        search_interval = 0
        while self.__search_flag:
            dur = time.time()
            self.__iface.scan()
            search_interval = min(search_interval + 0.5, 5)
            while time.time() - dur < search_interval:
                if not self.__search_flag:
                    return
                time.sleep(0.5)
            devices = self.__iface.scan_results()
            for device in devices:
                if "iRe" not in device.ssid:
                    continue
                if device.ssid not in added_devices:
                    added_devices.add(device.ssid)
                    self.device_queue.put([device.ssid, device.bssid[:-1], device.ssid])

    def _get_default_gateway(
        self, timeout=2
    ):  # TODO: some problems under multiple interfaces
        start = time.time()
        while time.time() - start < timeout:
            gateways = netifaces.gateways()
        try:
            for ips in gateways[netifaces.AF_INET]:
                if ips[1] == str(self.__iface._raw_obj["guid"]):
                    return ips[0]
        except Exception:
            pass
        return None

    def _get_connected_wifi_name(self):
        iface = str(self.__iface._raw_obj["guid"])[1:-1]
        try:
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"], creationflags=0x08000000
            )
            output = output.decode(locale.getpreferredencoding())
            for profile in output.split("\r\n\r\n"):
                if iface.lower() in profile.lower():
                    lines = profile.split("\n")
                    for line in lines:
                        if "ssid" in line.lower():
                            return line.split(":")[1].strip()
        except subprocess.CalledProcessError:
            print_exc()
        return None

    def stop(self):
        self.__search_flag = False

    def connect(self, ssid):
        self.stop()
        if self._get_connected_wifi_name() == ssid:  # return if connected
            host = self._get_default_gateway(timeout=1)
            if host is not None:
                return (host, self.port)
        self.__iface.disconnect()
        time.sleep(2)
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile = self.__iface.add_network_profile(profile)
        for i in range(5):
            self.__iface.connect(profile)
            time.sleep(0.5 * (i + 1))
            if self.__iface.status() == pywifi.const.IFACE_CONNECTED:
                time.sleep(1)
                host = self._get_default_gateway(timeout=2)
                if host is not None:
                    return (host, self.port)
            print("...Retry connecting:", i + 1)
        if "usb" in self.__iface.name().lower():
            self.__iface.remove_all_network_profiles()
            self.__iface.disconnect()
        warn = "Wi-Fi connection failed, please retry.\nFor encrypted device, connect through system wifi setting first."
        raise Exception(warn)
