import math
import re
from datetime import datetime
from queue import Queue
from threading import Thread

import numpy as np


class Parser:
    def __init__(self, chs, fs,queue: Queue):
        self.queue = queue
        self.chs = chs
        self.ch_bytes = 3
        self.batt_val = -1
        self.__start = 2
        self.__checksum = -4
        self.__trigger = -3
        self.__battery = -2
        self.__packet = -1
        self.imp_flag = False
        self._ratio = 0.02235174
        self.imp_len = int(512 * 2 * fs / 500)
        self.imp_factor = 1000 / 6 / (self.imp_len / 2) * math.pi / 4
        length = self.chs * self.ch_bytes + abs(self.__checksum)
        self.__pattern = re.compile(b"\xbb\xaa.{%d}" % length, flags=re.DOTALL)
        self.threshold = int((self.__start + length) * fs * 0.01)
        self.clear_buffer()

    def clear_buffer(self):
        self.__buffer = bytearray()
        self.__last_num = 255
        self.packet_drop_count = 0
        self.__impe_queue = np.zeros((self.imp_len, self.chs))
        self.imp_idx = 0

    def _cal_imp(self, data_queue):
        for data in data_queue:
            self.__impe_queue[self.imp_idx] = data[: self.chs]
            self.imp_idx += 1
            if self.imp_idx == self.imp_len:
                task = Thread(
                    target=self._get_impedance,
                    args=(self.__impe_queue.copy(),),
                    daemon=True,
                )
                task.start()
                self.imp_idx = 0

    def _get_impedance(self, data):
        iserror = np.sum(np.abs(data) <= 4000000 * self._ratio, axis=0) / self.imp_len
        freq_data = np.fft.fft(data, axis=0)
        tt = np.max(np.abs(freq_data[62:67]), axis=0)
        impe_data = np.abs(tt * self.imp_factor - 5000).astype(int)
        impe_data = np.where(iserror <= 0.2, math.inf, impe_data).tolist()
        if self.imp_flag:
            self.queue.put(impe_data)

    def parse_data(self, q: bytes) -> list[list[float]]:
        self.__buffer.extend(q)
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
            if self.imp_flag:
                self._cal_imp(data_list)
            else:
                self.queue.put(data_list)
            del self.__buffer[: frame_obj.end()]
            # print(f"parsed{len(data_list)},{datetime.now()}")
            self.batt_val = frame[self.__battery]
