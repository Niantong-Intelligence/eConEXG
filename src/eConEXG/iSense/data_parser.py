import ctypes
import math
from pathlib import Path
from platform import system
import re
from datetime import datetime
from threading import Thread
import numpy as np


class Parser:
    # signal format
    ch_bytes = 3
    _seq = 8
    _trig = _seq + 2
    __bat = _trig + 2
    _start = __bat + 8
    _ratio = 0.02235174

    def __init__(self, fs=2000, eeg_chs=128, emg_chs=8):
        class Witharray(ctypes.Structure):
            _fields_ = [("data", ctypes.c_double * 136)]

        suff = (
            "dll"
            if system() == "Windows"
            else ("dylib" if system() == "Darwin" else "so")
        )
        base = str(Path(__file__).parent.joinpath("transform." + suff))
        self.__parser = ctypes.CDLL(base)
        self.__parser.function.argtypes = [ctypes.c_char_p]
        self.__parser.function.restype = Witharray
        self.eeg_chs = eeg_chs
        self.emg_chs = emg_chs
        self.fs = fs
        self.batt_val = 0
        # impedance params
        self.imp_len = int(512 * 2 * fs / 500)
        self.imp_factor = 1000 / 6 / (self.imp_len / 2) * math.pi / 4
        # parser related
        self.vld_chs = self.eeg_chs + self.emg_chs  # convert to hw chs
        self.length = (
            int(self.vld_chs / 8 * 9) * self.ch_bytes + self._start - self._seq
        )
        ptn = b"\xc6\x91\x19\x99\x27\x02\x19\x42.{%d}" % self.length
        self.__pattern = re.compile(ptn, flags=re.DOTALL)
        self.pkt_size = self._get_ch_index()
        self.clear_buffer()

    # get block size
    def _get_ch_index(self) -> int:
        """
        Return: data block size in frames

        """
        length = self.length + self._seq
        block_duration = 0.013 if self.fs >= 2000 else 0.008
        return max(int(length * self.fs * block_duration / 512) * 512, 512)

    def clear_buffer(self):
        self.__buffer = bytearray()
        self._last = 255
        self.packet_drop_count = 0
        self.__impe_queue = np.zeros((self.imp_len, self.vld_chs), dtype=np.float32)
        self.imp_idx = 0
        self.imp_flag = False
        self.impedance = None

    def _cal_imp(self, data_queue):
        for data in data_queue:
            self.__impe_queue[self.imp_idx] = data[: self.vld_chs]
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
        # major time consumption np.fft.fft
        freq_data = np.fft.fft(data, axis=0)
        tt = np.max(np.abs(freq_data[62:67]), axis=0)
        impe_data = np.abs(tt * self.imp_factor - 5000).astype(int)
        impe_data = np.where(iserror <= 0.2, math.nan, impe_data).tolist()
        if self.imp_flag:
            self.impedance = impe_data

    def parse_data(self, q: bytes) -> list[list[int]]:
        self.__buffer.extend(q)
        if len(self.__buffer) < self.pkt_size:
            return
        frames = []
        for frame_obj in self.__pattern.finditer(self.__buffer):
            frame = frame_obj.group()
            cur = frame[self._seq]
            if cur != ((self._last + 1) % 256) or cur != frame[self._seq + 1]:
                self.packet_drop_count += 1
                err = f"\n>>>> Pkt Los Cur:{cur} Last valid:{self._last}. {datetime.now()}, dropped packets:{self.packet_drop_count}<<<<"
                print(err)
            self._last = cur
            data = self.__parser.function(frame[self._start :]).data[: self.vld_chs]
            data.append(frame[self._trig + 1])  # trigger
            frames.append(data)
        if frames:
            del self.__buffer[: frame_obj.end()]
            self.batt_val = frame[self.__bat]
            if self.imp_flag:
                self._cal_imp(frames)
                return
            return frames
