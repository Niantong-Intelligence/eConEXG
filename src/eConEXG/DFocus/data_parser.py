import re
from datetime import datetime


class Parser:
    _byts = 3
    _imu_bytes = 2
    _ratio = 0.02235174
    _imu_ratio = 1 / 100
    _header = 2
    _fall_off = 38
    _batt = 39
    _checksum = 40
    _seq = -1

    _eegs = 10 * _byts
    _imus = 3 * _imu_bytes
    _length = _header + _eegs + _imus + 4

    def __init__(self) -> None:
        self.__buffer = bytearray()
        self.eeg_idx = [i * self._byts + self._header for i in range(5)]
        self.imu_start = self._eegs + self._header
        self.imu_idx = [
            i + self.imu_start for i in range(0, self._imus, self._imu_bytes)
        ]
        self.__pattern = re.compile(
            b"\xbb\xaa.{%d}" % (self._length-2), flags=re.DOTALL
        )
        self.fallof = 1
        self.battery = 0
        self.clear_buffer()

    def clear_buffer(self):
        del self.__buffer[:]
        self.__last = 255
        self.__drop = 0

    def parse_data(self, q: bytes) -> list[list[float]]:
        self.__buffer.extend(q)
        if len(self.__buffer) < self._length:
            return
        frames = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = memoryview(frame_obj.group())
            if (
                frame[self._checksum] != ~sum(frame[self._header: self._checksum]) & 0xFF
            ):
                err = f"|Frame Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self._seq]
            if cur_num != ((self.__last + 1) % 256):
                self.__drop += 1
                err = f">>>> EEG Pkt Los Cur:{cur_num} Last valid:{self.__last} buf len:{len(self.__buffer)} dropped: {self.__drop} times {datetime.now()}<<<<\n"
                print(err)
            self.__last = cur_num

            eeg = [
                [
                    int.from_bytes(
                        frame[i : i + self._byts],
                        signed=True,
                        byteorder="big",
                    ) * self._ratio,
                    int.from_bytes(
                        frame[i + 15: i + 15 + self._byts],
                        signed=True,
                        byteorder="big",
                    ) * self._ratio
                ]
                for i in self.eeg_idx
            ]
            imu = [
                int.from_bytes(
                    frame[i : i + self._imu_bytes],
                    signed=True,
                    byteorder="little",
                )
                * self._imu_ratio
                for i in self.imu_idx
            ]
            eeg.append(imu)
            frames.append(eeg)
            self.fallof = frame[self._fall_off]
            self.battery = frame[self._batt]
        if frames:
            del self.__buffer[: frame_obj.end()]
            return frames


if __name__ == "__main__":
    parser = Parser()
    print(vars(parser))
