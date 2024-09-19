import re
from datetime import datetime


class Parser:
    _byts = 3
    _imu_bytes = 2
    _ratio = 0.02235174
    _header = 2
    _emg_chs = 8
    _emg_frames = 8
    _emgs = _emg_frames * _emg_chs * _byts  # 8 frames per packet
    _imu_chs = 6
    _imus = _imu_chs * _imu_bytes

    _preserved = -7
    _checksum = -3
    _bat = -2
    _seq = -1

    def __init__(self) -> None:
        self.__buffer = bytearray()
        offset = self._header
        self.emg_idx = [i + offset for i in range(0, self._emgs, self._byts)]
        offset += self._emgs
        self.imu_idx = [i + offset for i in range(0, self._imus, self._imu_bytes)]
        offset += self._imus

        self.__pattern = re.compile(
            b"\xbb\xaa.{%d}" % (offset + abs(self._preserved) - 2), flags=re.DOTALL
        )
        self.threshold = offset + abs(self._preserved)
        self.clear_buffer()

    def clear_buffer(self):
        del self.__buffer[:]
        self.__last = 255
        self.__drop = 0

    def parse_data(self, q: bytes) -> list[list[float]]:
        self.__buffer.extend(q)
        if len(self.__buffer) < self.threshold:
            return
        frames = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = memoryview(frame_obj.group())
            if (
                frame[self._checksum]
                != (~sum(frame[self._header : self._preserved]))& 0xFF
            ):
                err = f"|EEG Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self._seq]
            if cur_num != ((self.__last + 1) % 256):
                self.__drop += 1
                err = f">>>> EEG Pkt Los Cur:{cur_num} Last valid:{self.__last} buf len:{len(self.__buffer)} dropped: {self.__drop} times {datetime.now()}<<<<\n"
                print(err)
            self.__last = cur_num

            emg = [
                int.from_bytes(
                    frame[i : i + self._byts],
                    signed=True,
                    byteorder="big",
                )
                * self._ratio
                for i in self.emg_idx
            ]
            emg = [
                emg[i : i + self._emg_frames]
                for i in range(0, len(emg), self._emg_frames)
            ]
            imu = [
                int.from_bytes(
                    frame[i : i + self._imu_bytes],
                    signed=True,
                    byteorder="little",
                )
                for i in self.imu_idx
            ]
            emg.append(imu)
            frames.append(emg)
        if frames:
            del self.__buffer[: frame_obj.end()]
            return frames


if __name__ == "__main__":
    parser = Parser()
    print(vars(parser))
