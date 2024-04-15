from typing import Optional
import time


class triggerBoxWireless:
    def __init__(self) -> None:
        from serial import Serial
        from serial.tools.list_ports import comports

        ports = comports()
        for port in ports:
            if port.pid == 0x6001 and port.vid == 0x0403:
                self.dev = Serial(port.device, baudrate=115200, timeout=1)
                break
        else:
            raise Exception("Trigger box not found")

    def sendMarker(self, marker: int):
        if not isinstance(marker, int):
            marker = int(marker)
        if marker == 13 or marker <= 0 or marker > 255:
            raise Exception("Invalid marker")
        self.dev.write(marker.to_bytes() + b"\x55\x66\x0d")

    def close_dev(self):
        self.dev.close()


class triggerBoxWired:
    def __init__(self) -> None:
        from serial import Serial
        from serial.tools.list_ports import comports

        ports = comports()
        for port in ports:
            if port.pid == 0x5740 and port.vid == 0x0483:
                self.dev = Serial(port.device, timeout=1)
                break
        else:
            raise Exception("Trigger box not found")

    def sendMarker(self, marker: int):
        if not isinstance(marker, int):
            marker = int(marker)
        if marker <= 0 or marker > 255:
            raise Exception("Invalid marker")
        self.dev.write(marker.to_bytes())

    def close_dev(self):
        self.dev.close()


class lightStimulator:
    def __init__(self) -> None:
        from serial import Serial
        from serial.tools.list_ports import comports

        self.channels = 6
        ports = comports()
        for port in ports:
            if (
                port.pid == 0x6001
                and port.vid == 0x0403
                and (
                    "LIGHTSTIMA" in port.serial_number
                    or "LIGHTSTIM" in port.serial_number
                )
            ):
                self.dev = Serial(port.device, baudrate=115200, timeout=1)
                time.sleep(0.1)
                self.dev.read_all()
        else:
            raise Exception("Light stimulator not found")

    def vep_mode(self, fs: list[Optional[float]]=[]):
        for i in range(self.channels):
            if i > len(fs):
                continue
            if fs[i] is not None:
                command = f"AT+VEP={i+1},{fs[i]}\r\n".encode()
                self.dev.write(command)
                # time.sleep(0.02)
        time.sleep(0.05)
        print(self.dev.readall())

    def erp_mode(self, fs: float):
        command = f"AT+ERP=,{fs}\r\n".encode()
        self.dev.write(command)

    def __del__(self):
        if hasattr(self, "dev"):
            self.dev.close()
