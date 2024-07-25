from typing import Optional
import time


class triggerBoxWireless:
    def __init__(self, port: str = None):
        """
        Args:
            port: The serial port of the trigger box. If not given,
                the function will try to find the trigger box automatically.

        Raises:
            Exception: If the trigger box is not found.
        """
        from serial import Serial
        from serial.tools.list_ports import comports

        if not port:
            for ports in comports():
                if ports.pid == 0x6001 and ports.vid == 0x0403:
                    port = ports.device
                    break
            else:
                raise Exception("Trigger box not found")
        self.dev = Serial(port, baudrate=115200, timeout=1)
        self.__last_timestamp = time.perf_counter()
        self.__warn = "Marker interval too short, amplifier may fail to receive it. Suggested interval is above 50ms"
        time.sleep(0.1)

    def sendMarker(self, marker: int):
        """
        Send a marker to the trigger box.

        Args:
            marker: range from `1` to `255`, `13` is not available and reserved for internal use.

        Raises:
            Exception: If the marker is invalid.
        """
        if time.perf_counter() - self.__last_timestamp < 0.04:
            print(self.__warn)
        if not isinstance(marker, int):
            marker = int(marker)
        if marker == 13 or marker <= 0 or marker > 255:
            raise Exception("Invalid marker")
        marker = marker.to_bytes(length=1, byteorder="big", signed=False)
        self.dev.write(marker + b"\x55\x66\x0d")
        self.__last_timestamp = time.perf_counter()

    def close_dev(self):
        self.dev.close()


class triggerBoxWired:
    def __init__(self, port: str = None):
        """
        Args:
            port: The serial port of the trigger box. If not given,
                the function will try to find the trigger box automatically.

        Raises:
            Exception: If the trigger box is not found.
        """
        from serial import Serial
        from serial.tools.list_ports import comports

        if not port:
            for ports in comports():
                if ports.pid == 0x5740 and ports.vid == 0x0483:
                    port = ports.device
                    break
            else:
                raise Exception("Trigger box not found")
        self.dev = Serial(port, timeout=1)

    def sendMarker(self, marker: int):
        """
        Send a marker to the trigger box.

        Args:
            marker: range from `1` to `255`.

        Raises:
            Exception: If the marker is invalid.
        """
        if not isinstance(marker, int):
            marker = int(marker)
        if marker <= 0 or marker > 255:
            raise Exception("Invalid marker")
        self.dev.write(marker.to_bytes(length=1, byteorder="big", signed=False))

    def close_dev(self):
        self.dev.close()


class lightStimulator:
    def __init__(self, port: str = None):
        from serial import Serial
        from serial.tools.list_ports import comports

        self.wait_time = 0.1
        self.channels = 6

        if not port:
            for ports in comports():
                if (
                    ports.pid == 0x6001
                    and ports.vid == 0x0403
                    and ports.serial_number in ["LIGHTSTIMA", "LIGHTSTIM"]
                ):
                    port = ports.device
                    break
            else:
                raise Exception("Light stimulator not found")
        self.dev = Serial(port, baudrate=115200, timeout=2)
        self.dev.read_all()

    def vep_mode(self, fs: list[Optional[float]] = [1, 1, 1, 1, 1, 1]):
        """
        Enter VEP mode, which allows you to control the frequency of each channel separately.

        Args:
            fs: List of frequencies in Hz, range from 0 to 100 with 0.1Hz resolution.
                If a corresponding frequency is None, 0  or not given, it will be set to off.

        Raises:
            Exception: If the frequency is invalid or hardware error.
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
        if b"SSVEP MODE OK" not in ret:
            raise Exception("Failed to set VEP mode")

    def erp_mode(self, fs: float):
        """
        Enter ERP mode, which allows you to control the frequency of all channels at once.

        Args:
            fs: Frequency in Hz, range from 0 to 100 with 0.1Hz resolution.

        Raises:
            Exception: If the frequency is invalid or hardware error.
        """
        fs = self._validate_fs(fs)
        command = f"AT+ERP={fs:.1f}\r\n".encode()
        self.dev.write(command)
        time.sleep(self.wait_time)
        ret = self.dev.read_all()
        if b"ERP MODE OK" not in ret:
            raise Exception("Failed to set VEP mode")

    def _validate_fs(self, fs: Optional[float]):
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
