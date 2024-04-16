import re
from datetime import datetime


class Parser:
    def __init__(self, bat) -> None:
        self.__buffer = b""
        self.__pattern = re.compile(b"\xbb\xaa.{18}", flags=re.DOTALL)
        self.__imu_pattern = re.compile(b"\xdd\xcc.{8}", flags=re.DOTALL)
        self.bat = bat
        self.eeg_last = 255
        self.imu_last = 255
        self.ch_bytes = 3
        self.imu_bytes = 2
        self.scale_ratio = 0.02235174
        self.total = 0

    def parse(self, q):
        self.__buffer += q
        eeg_list: list[bytes] = self.__pattern.findall(self.__buffer)
        self.__buffer = self.__pattern.sub(b"", self.__buffer)
        frames = []
        for frame in eeg_list:
            self.total += 5
            cur = frame[19]  # packet sequence
            if cur != ((self.eeg_last + 1) % 256):
                temp = f"eeg丢包,上一个包序号：{self.eeg_last}，当前包序号：{cur}, total:{self.total}, {datetime.now()}"
                print(temp)
            self.eeg_last = cur

            if frame[18] != sum(frame[2:18]) & 0xFF:
                print("eeg checksum error")
                continue
            raw = frame[2:17]
            data = [
                [
                    int.from_bytes(
                        raw[i : i + self.ch_bytes], signed=True, byteorder="little"
                    )
                    * self.scale_ratio
                ]
                for i in range(0, len(raw), self.ch_bytes)
            ]
            frames.extend(data)  # length = 5

        emg_list: list[bytes] = self.__imu_pattern.findall(self.__buffer)
        # self.__buffer = self.__imu_pattern.sub(b"", self.__buffer)
        self.__buffer = self.__imu_pattern.split(self.__buffer)[-1]
        for frame in emg_list:
            cur = frame[9]
            if cur != ((self.imu_last + 1) % 256):
                temp = f"imu丢包,上一个包序号：{self.imu_last}，当前包序号：{cur}"
                print(temp)
            self.imu_last = cur
            raw = frame[2:8]
            if frame[8] != sum(raw) & 0xFF:
                print("imu checksum error")
                continue
            data = [
                int.from_bytes(
                    raw[i : i + self.imu_bytes], signed=True, byteorder="little"
                )
                / 100
                for i in range(0, len(raw), self.imu_bytes)
            ]
            frames.append(data)  # length = 3
        return frames
