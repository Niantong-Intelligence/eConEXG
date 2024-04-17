import re
from datetime import datetime


class Parser:
    HOTKEY_TRIGGER = -2
    BATTERY = -1
    _start = 2
    _checksum = -3
    _battery = -2
    _packet = -1

    def __init__(
        self,
        imu: bool = True,
        num_channels=8,
        bytes_per_channel=3,
        max_packet_num=256,
        fms_per_pkt=9,
        scale_ratio=0.02235174,
    ) -> None:
        self.imu_channels = 0
        self.imu = imu
        if imu:
            self.imu_channels = 6
        self.bytes_per_imu = 2

        self.num_channels = num_channels
        self.ch_bytes = bytes_per_channel
        self.max_packet_num = max_packet_num
        self.scale_ratio = scale_ratio
        self.fms_per_pkt = fms_per_pkt

        length = (
            self.num_channels * self.ch_bytes * self.fms_per_pkt
            + self.bytes_per_imu * self.imu_channels
            + abs(self._checksum)
        )
        self.__pattern = re.compile(b"\xbb\xaa.{%d}" % length, flags=re.DOTALL)
        self.clear_buffer()

    def clear_buffer(self):
        self.__buffer = b""
        self.__last_num = 255
        self.packet_drop_count = 0

    def parse_data(self, q: bytes):
        self.__buffer += q
        frame_list: list[bytes] = self.__pattern.findall(self.__buffer)
        self.__buffer = self.__pattern.split(self.__buffer)[-1]
        data_list = []

        for frame in frame_list:
            raw = frame[self._start : self._checksum]
            if frame[self._checksum] != (~sum(raw)) & 0xFF:
                err = f"|Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self._packet]

            if cur_num != ((self.__last_num + 1) % 256):
                self.packet_drop_count += 1
                err = f">>>> Pkt Los Cur:{cur_num} Last valid:{self.__last_num} buf len:{len(self.__buffer)} dropped packets:{self.packet_drop_count} {datetime.now()}<<<<\n"
                print(err)
            self.__last_num = cur_num

            channels = [
                int.from_bytes(raw[i : i + self.ch_bytes], signed=True,byteorder='big')
                for i in range(
                    0,
                    len(raw) - self.imu_channels * self.bytes_per_imu,
                    self.ch_bytes,
                )
            ]
            imu_data = []
            if self.imu:
                raw = raw[-self.imu_channels * self.bytes_per_imu :]
                imu_data = [
                    int.from_bytes(raw[i : i + self.bytes_per_imu], signed=True,byteorder='big')
                    for i in range(0, len(raw), self.bytes_per_imu)
                ]

            for channel in range(self.fms_per_pkt):
                data = channels[
                    channel * self.num_channels : (channel + 1) * self.num_channels
                ]
                data.extend(imu_data)
                data.append(0)  # cus trigger
                data.append(frame[self._battery])
                data_list.append(data)
        return data_list
