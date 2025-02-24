import time
from pathlib import Path
from platform import system
from traceback import print_exc

import usb.backend.libusb1
import usb.core
import usb.util


class iSenseUSB:
    out_point = 0x02
    in_point = 0x86
    pref = b"\x55\xa5"
    suffix = b"\x02\xf0\xf0\xf0\xf0"
    mode = {
        b"Z": b"\x00",
        b"W": b"\x01",
        b"S": b"\x02",
        b"T": b"\x03",
        b"R": b"\xaa\x5a\x03\x02\x11\x11\x11\xf0",
    }
    fss = {
        250: b"\x06",
        500: b"\x05",
        1000: b"\x04",
        2000: b"\x03",
        4000: b"\x02",
        8000: b"\x01",
        16000: b"\x00",
    }

    def __init__(self, fs, pkt_size=4096 * 2):
        super().__init__()
        self.fs = fs
        self.idVendor = 0x04B4
        self.idProduct = 0x00F1
        self.pkt_size = pkt_size
        self.delay = 0.05

    def _cmd(self, mode, fs=None):
        if mode == b"R":
            return self.mode[mode]
        if fs is None:
            fs = self.fs
        return self.pref + self.mode[mode] + self.fss[fs] + self.suffix

    def connect_socket(self):
        def load_base(*args, **kwargs):
            return str(Path(__file__).parent.joinpath("libusb-1.0." + suff))

        suff = (
            "dll"
            if system() == "Windows"
            else ("dylib" if system() == "Darwin" else None)
        )
        base = load_base if suff else None
        base = usb.backend.libusb1.get_backend(find_library=base)
        devs = usb.core.find(
            idVendor=self.idVendor,
            idProduct=self.idProduct,
            find_all=True,
            backend=base,
        )
        self._socket = None
        for dev in devs:
            self._socket = dev
        if self._socket is None:
            devs = usb.core.find(
                idVendor=0x8001,
                idProduct=0x0001,
                find_all=True,
                backend=base,
            )
            for dev in devs:
                self._socket = dev
            if self._socket is None:
                raise ValueError("Device not found!")
        try:
            self._socket.set_configuration()
        except Exception:
            print_exc()
            raise Exception("Driver issue! Please reinstall hardware driver.")

    def close_socket(self):
        try:
            self._socket.write(self.out_point, self._cmd(b"R"))
            time.sleep(self.delay)
        except Exception:
            pass
        usb.util.dispose_resources(self._socket)
        time.sleep(self.delay)

    def start_impe(self):
        self._socket.write(self.out_point, self._cmd(b"Z"))
        time.sleep(self.delay)

    def start_data(self):
        self._socket.write(self.out_point, self._cmd(b"W"))
        time.sleep(self.delay)
        self.recv_socket()

    def recv_socket(self):
        return self._socket.read(self.in_point, self.pkt_size)

    def stop_recv(self):
        self._socket.write(self.out_point, self._cmd(b"R"))
        time.sleep(self.delay)

    def get_endpoint(self):
        cfg = self._socket.get_active_configuration()
        print("cfg", cfg)
        intf = cfg[(0, 0)]
        ep = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )
        print("ep:", ep)
        assert ep is not None


if __name__ == "__main__":
    dev = iSenseUSB(fs=8000)
    dev.connect_socket()
    dev.get_endpoint()
