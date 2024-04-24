import re
from datetime import datetime


class Parser:
    _byts = 3
    _imu_bytes = 2
    _ratio = 0.02235174
    _imu_ratio = 1 / 100
    _header = 2

    _eegs = 5 * _byts
    _imus = 3 * _imu_bytes

    def __init__(self) -> None:
        self.__buffer = bytearray()
        self.__pattern = re.compile(b"\xbb\xaa.{18}\xdd\xcc.{8}", flags=re.DOTALL)
        self.eeg_idx = [i + self._header for i in range(0, self._eegs, self._byts)]
        self.eeg_fall = self._header + self._eegs
        self.eeg_checksum = self.eeg_fall + 1
        self.eeg_seq = self.eeg_checksum + 1
        self.imu_start = self.eeg_seq + self._header + 1
        self.imu_idx = [
            i + self.imu_start for i in range(0, self._imus, self._imu_bytes)
        ]
        self.imu_checksum = self.imu_start + self._imus
        self.imu_seq = self.imu_checksum + 1
        self._threshold = self.imu_seq + 1
        self.clear_buffer()

    def clear_buffer(self):
        del self.__buffer[:]
        self.eeg_last = 255
        self.imu_last = 255
        self.__drop_eeg = 0
        self.__drop_imu = 0

    def parse_data(self, q: bytes) -> list[list[float]]:
        self.__buffer.extend(q)
        if len(self.__buffer) < self._threshold:
            return
        frames = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = memoryview(frame_obj.group())
            if (
                frame[self.eeg_checksum]
                != sum(frame[self._header : self.eeg_checksum]) & 0xFF
            ):
                err = f"|EEG Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            if (
                frame[self.imu_checksum]
                != sum(frame[self.imu_start : self.imu_checksum]) & 0xFF
            ):
                err = f"|IMU Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self.eeg_seq]
            if cur_num != ((self.eeg_last + 1) % 256):
                self.__drop_eeg += 1
                err = f">>>> EEG Pkt Los Cur:{cur_num} Last valid:{self.eeg_seq} buf len:{len(self.__buffer)} dropped: {self.__drop_eeg} times {datetime.now()}<<<<\n"
                print(err)
            self.eeg_last = cur_num
            cur_num = frame[self.imu_seq]
            if cur_num != ((self.imu_last + 1) % 256):
                self.__drop_imu += 1
                err = f">>>> IMU Pkt Los Cur:{cur_num} Last valid:{self.imu_seq} buf len:{len(self.__buffer)} dropped: {self.__drop_imu} times {datetime.now()}<<<<\n"
                print(err)
            self.imu_last = cur_num

            eeg = [
                [
                    int.from_bytes(
                        frame[i : i + self._byts],
                        signed=True,
                        byteorder="little",
                    )
                    * self._ratio
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
        if frames:
            del self.__buffer[: frame_obj.end()]
            return frames


if __name__ == "__main__":
    parser = Parser()
    print(vars(parser))
