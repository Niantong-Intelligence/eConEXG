import math
import re
from datetime import datetime
from queue import Queue

import numpy as np


class Parser:
    def __init__(self, chs, fs):
        self.num_channels = chs
        self.ch_bytes = 3
        self.batt_val = -1
        self.__start = 2
        self.__checksum = -4
        self.__trigger = -3
        self.__battery = -2
        self.__packet = -1
        self._ratio = 0.02235174
        self.imp_len = int(512 * 2 * fs / 500)
        self.imp_factor = 1000 / 6 / (self.imp_len / 2) * math.pi / 4
        length = self.num_channels * self.ch_bytes + abs(self.__checksum)
        self.__pattern = re.compile(b"\xbb\xaa.{%d}" % length, flags=re.DOTALL)
        self.threshold = int((self.__start + length) * fs * 0.005)
        self.clear_buffer()

    def clear_buffer(self):
        self.__buffer = bytearray()
        self.__last_num = 255
        self.packet_drop_count = 0
        self.__impe_queue = np.zeros(
            (self.imp_len, self.num_channels), dtype=np.float32
        )
        self.imp_idx = 0

    def cal_imp(self, data_queue, imp_queue: Queue):
        for data in data_queue:
            self.__impe_queue[self.imp_idx] = data[: self.num_channels]
            self.imp_idx += 1
            if self.imp_idx == self.imp_len:
                impe_data = self._get_impedance(self.__impe_queue)
                imp_queue.put(impe_data)
                self.imp_idx = 0

    def _get_impedance(self, data):
        iserror = np.sum(np.abs(data) <= 4000000 * self._ratio, axis=0) / self.imp_len
        freq_data = np.fft.fft(data, axis=0)
        tt = np.max(np.abs(freq_data[62:67]), axis=0)
        impe_data = np.abs(tt * self.imp_factor - 5000).astype(int)
        impe_data = np.where(iserror <= 0.2, math.inf, impe_data).tolist()
        return impe_data

    def parse_data(self, q: bytes, recv_queue: Queue) -> list[list[float]]:
        self.__buffer.extend(q)
        self.__buffer.find
        if len(self.__buffer) < self.threshold:
            return self.batt_val
        data_list = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = frame_obj.group()
            raw = frame[self.__start : self.__checksum]
            if frame[self.__checksum] != (~sum(raw)) & 0xFF:
                err = f"|Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self.__packet]
            if cur_num != ((self.__last_num + 1) % 256):
                self.packet_drop_count += 1
                err = f">>>> Pkt Los Cur:{cur_num} Last valid:{self.__last_num} buf len:{len(self.__buffer)} dropped times:{self.packet_drop_count} {datetime.now()}<<<<\n"
                print(err)
            self.__last_num = cur_num
            data = [
                int.from_bytes(raw[i : i + self.ch_bytes], signed=True, byteorder="big")
                * self._ratio
                for i in range(0, len(raw), self.ch_bytes)
            ]  # default byteorder="big"
            data.append(frame[self.__trigger])
            data_list.append(data)
        if data_list:
            # print(f"parsed{len(data_list)},{datetime.now()}")
            recv_queue.put(data_list)
            del self.__buffer[: frame_obj.end()]
            self.batt_val = frame[self.__battery]
        return self.batt_val
