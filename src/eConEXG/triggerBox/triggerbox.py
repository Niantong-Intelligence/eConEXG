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
        self.__last_timestamp = time.perf_counter()
        self.__warn = "Marker interval too short, amplifier may fail to receive it. Suggested interval is above 50ms"
        time.sleep(0.1)

    def sendMarker(self, marker: int):
        if time.perf_counter() - self.__last_timestamp < 0.045:
            print(self.__warn)
        if not isinstance(marker, int):
            marker = int(marker)
        if marker == 13 or marker <= 0 or marker > 255:
            raise Exception("Invalid marker")
        self.dev.write(marker.to_bytes() + b"\x55\x66\x0d")
        self.__last_timestamp = time.perf_counter()

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

        self.wait_time = 0.1
        self.channels = 6
        ports = comports()
        for port in ports:
            if (
                port.pid == 0x6001
                and port.vid == 0x0403
                and port.serial_number in ["LIGHTSTIMA", "LIGHTSTIM"]
            ):
                self.dev = Serial(port.device, baudrate=115200, timeout=2)
                self.dev.read_all()
                break
        else:
            raise Exception("Light stimulator not found")

    def vep_mode(self, fs: list[Optional[float]] = [1, 1, 1, 1, 1, 1]):
        """
        Parameters
        ----------
        fs : list, default [1,1,1,1,1,1]
            List of frequencies in Hz, range from 0 to 100 with 0.1Hz resolution.
            If a corresponding frequency is None, 0  or not given, it will be set to off.
        """
        fss = fs.copy()
        if len(fss) < self.channels:
            fss += [0] * (self.channels - len(fss))
        for i in range(self.channels):
            fss[i] = self._validate_fs(fss[i])
        command = ",".join([f"{f:.1f}" for f in fss[: self.channels]])
        command = f"AT+VEP={command}\r\n".encode()
        self.dev.write(command)
        time.sleep(self.wait_time)
        ret = self.dev.read_all()
        print(ret)
        if b"SSVEP MODE OK" not in ret:
            raise Exception("Failed to set VEP mode")

    def erp_mode(self, fs: float):
        fs = self._validate_fs(fs)
        command = f"AT+ERP={fs:.1f}\r\n".encode()
        self.dev.write(command)
        time.sleep(self.wait_time)
        ret = self.dev.read_all()
        print(ret)
        if b"ERP MODE OK" not in ret:
            raise Exception("Failed to set VEP mode")

    def _validate_fs(self, fs: float):
        if not isinstance(fs, (int, float)):
            if fs is None:
                fs = 0
            else:
                raise Exception("Invalid frequency")
        if fs > 100 or fs < 0:
            raise Exception("Invalid frequency")
        return fs

    def close_dev(self):
        self.dev.close()
