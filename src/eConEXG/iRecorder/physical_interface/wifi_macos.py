from queue import Queue
from threading import Thread
import subprocess
import locale
import netifaces
import time


class wifiMACOS(Thread):
    def __init__(self, device_queue: Queue):
        super().__init__(daemon=True)
        self.device_queue = device_queue
        self.port = 4321
        self.__search_flag = True
        self.__interface = self.validate_interface()

    @property
    def interface(self):
        return self.__interface.interfaceName()

    def validate_interface(self):
        from CoreWLAN import CWWiFiClient

        obj = CWWiFiClient.sharedWiFiClient().interface()
        if not obj.powerOn():
            raise Exception("Wi-Fi interface not on")
        return obj

    def _get_default_gateway(self, timeout=2):
        start = time.time()
        while time.time() - start < timeout:
            gateways = netifaces.gateways()
            try:
                for ips in gateways[netifaces.AF_INET]:  # TODO: KeyError: 2
                    if ips[1] == self.interface:
                        print(f"check{ips[0]}")
                        return ips[0]
            except Exception:
                pass
        return None

    def __request_location(self):
        from CoreLocation import CLLocationManager

        location_manager = CLLocationManager.alloc().init()
        # location_manager.requestAlwaysAuthorization()
        location_manager.requestWhenInUseAuthorization()
        location_manager.startUpdatingLocation()
        max_wait = 10
        for _ in range(1, max_wait):
            authorization_status = location_manager.authorizationStatus()
            if authorization_status == 3 or authorization_status == 4:
                return
            time.sleep(1)
        else:
            return "Unable to obtain authorisation"

    def run(self):
        ret = self.__request_location()
        if ret is not None:
            self.device_queue.put(f"Error during scanning: {ret}")
            return
        added_devices = set()
        while self.__search_flag:
            output, error = self.__interface.scanForNetworksWithName_error_(None, None)
            if error is not None:
                self.device_queue.put(f"Error during scanning: {error}")
                return
            if output is None:
                self.device_queue.put("Failed to scan WiFi devices.")
                return
            for network in output:
                ssid = network.ssid()  # 1:bssid, 2:rssi
                if "iRe" not in str(ssid):
                    continue
                if ssid not in added_devices:
                    added_devices.add(ssid)
                    self.device_queue.put([ssid, str(network.bssid()), ssid])

    def stop(self):
        self.__search_flag = False

    def connect(self, ssid):
        self.stop()
        # check if network already connected
        command = ["networksetup", "-getairportnetwork", self.interface]
        result = subprocess.check_output(command)
        result = result.decode(locale.getpreferredencoding()).split(":")
        if len(result) > 1:
            if result[1].strip() == ssid:
                host = self._get_default_gateway()
                if host:
                    return (host, self.port)
        # connect
        command = ["networksetup", "-setairportnetwork", self.interface, ssid]
        self.child_process = subprocess.Popen(command, stdout=subprocess.PIPE)
        out, _ = self.child_process.communicate()
        # process.wait()
        result = out.decode(locale.getpreferredencoding())
        if not result:
            host = self._get_default_gateway()
            if host:
                return (host, self.port)
        else:
            warn = "Wi-Fi connection failed, please retry.\nFor encrypted device, connect through system setting first."
            raise Exception(warn)

