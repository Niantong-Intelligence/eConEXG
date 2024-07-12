import re
from datetime import datetime
import numpy as np


class Parser:
    _byts = 3
    _start = 2
    _checksum = -4
    _trigger = -3
    _battery = -2
    _seq = -1
    _threshold_ratio = 0.01

    def __init__(self, chs):
        self.chs = chs
        self.batt_val = 0
        self.imp_flag = False
        self._ratio = 0.02235174
        length = self.chs * self._byts + abs(self._checksum)
        self.__pattern = re.compile(b"\xbb\xaa.{%d}" % length, flags=re.DOTALL)

    def _update_fs(self, fs):
        self._imp_len = int(512 * 2 * fs / 500)
        self._imp_factor = 1000 / 6 / (self._imp_len / 2) * np.pi / 4
        length = self.chs * self._byts + abs(self._checksum)
        self._threshold = int((self._start + length) * fs * self._threshold_ratio)
        self.clear_buffer()

    def clear_buffer(self):
        self.__buffer = bytearray()
        self.__last_num = 255
        self._drop_count = 0
        self.__impe_queue = np.zeros((self._imp_len, self.chs))
        self.__imp_idx = 0
        self.impedance = None

    def update_chs(self, chs: list[int]):
        self.ch_idx = chs[:]
        self.impedance = None

    def _cal_imp(self, frames):
        for data in frames:
            # filt trigger data
            self.__impe_queue[self.__imp_idx, self.ch_idx] = data[:-1]
            self.__imp_idx += 1
            if self.__imp_idx != self._imp_len:
                continue
            self._get_impedance(self.__impe_queue[:, self.ch_idx])
            self.__imp_idx = 0

    def _get_impedance(self, data):
        iserror = np.sum(np.abs(data) <= 4000000 * self._ratio, axis=0) / self._imp_len
        freq_data = np.fft.fft(data, axis=0)
        tt = np.max(np.abs(freq_data[62:67]), axis=0)
        impe_data = np.abs(tt * self._imp_factor - 5000).astype(int)
        impe_data = np.where(iserror <= 0.2, np.inf, impe_data).tolist()
        self.impedance = impe_data

    def parse_data(self, q: bytes) -> list[list[float]]:
        self.__buffer.extend(q)
        if len(self.__buffer) < self._threshold:
            return
        frames = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = memoryview(frame_obj.group())
            raw = frame[self._start : self._checksum]
            if frame[self._checksum] != (~sum(raw)) & 0xFF:
                self._drop_count += 1
                err = f"|Checksum invalid, packet dropped{datetime.now()}\n|Current:{frame.hex()}"
                print(err)
                continue
            cur_num = frame[self._seq]
            if cur_num != ((self.__last_num + 1) % 256):
                self._drop_count += 1
                err = f">>>> Pkt Los Cur:{cur_num} Last valid:{self.__last_num} buf len:{len(self.__buffer)} dropped times:{self._drop_count} {datetime.now()}<<<<\n"
                print(err)
            self.__last_num = cur_num
            data = [
                int.from_bytes(
                    raw[i * self._byts : (i + 1) * self._byts],
                    signed=True,
                    byteorder="big",
                )
                * self._ratio
                for i in self.ch_idx
            ]
            data.append(frame[self._trigger])
            frames.append(data)
        if frames:
            del self.__buffer[: frame_obj.end()]
            self.batt_val = frame[self._battery]
            if self.imp_flag:
                self._cal_imp(frames)
                return
            return frames
