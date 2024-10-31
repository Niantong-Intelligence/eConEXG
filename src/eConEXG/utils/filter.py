from scipy.signal import butter, iirnotch, lfilter, lfilter_zi
import numpy as np


class SignalFilter:
    def __init__(self, chs, fs) -> None:
        self.chs = chs
        self.start = 0
        self.end = chs
        self.fs = fs

        self.an = None
        self.ah = None
        self.al = None
        self.bn = None
        self.bh = None
        self.bl = None
        self.zin = None
        self.zih = None
        self.zil = None

        self.highpass = None
        self.notch = None
        self.lowpass = None

    def change_range(self, chs):
        self.chs = chs
        self.start = 0
        self.end = chs
        self.change_highpass(self.highpass)
        self.change_lowpass(self.lowpass)
        self.change_notch(self.notch)

    def change_highpass(self, highpass):
        self.highpass = highpass
        if self.highpass is not None:
            Wnh = self.highpass / (self.fs / 2)
            self.bh, self.ah, *_ = butter(2, Wnh, btype="high")
            zih = lfilter_zi(self.bh, self.ah)
            self.zih = np.array([zih for _ in range(self.chs)])

    def change_lowpass(self, lowpass):
        self.lowpass = lowpass
        if self.lowpass is not None:
            Wnl = self.lowpass / (self.fs / 2)
            self.bl, self.al, *_ = butter(2, Wnl, btype="low")
            zil = lfilter_zi(self.bl, self.al)
            self.zil = np.array([zil for _ in range(self.chs)])

    def change_notch(self, notch):
        self.notch = notch
        if self.notch is not None:
            self.bn, self.an = iirnotch(w0=self.notch, Q=30.0, fs=self.fs)
            notch_zi = lfilter_zi(self.bn, self.an)
            self.zin = np.array([notch_zi for _ in range(self.chs)])

    def l_filter(self, data: np.ndarray):
        if self.notch is not None:
            data[self.start: self.end, :], self.zin = lfilter(
                self.bn, self.an, data[self.start: self.end, :], axis=1, zi=self.zin
            )
        if self.highpass is not None:
            data[self.start: self.end, :], self.zih = lfilter(
                self.bh, self.ah, data[self.start: self.end, :], axis=1, zi=self.zih
            )
        if self.lowpass is not None:
            data[self.start: self.end, :], self.zil = lfilter(
                self.bl, self.al, data[self.start: self.end, :], axis=1, zi=self.zil
            )
