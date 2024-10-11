from datetime import datetime
from queue import Queue
from threading import Event, Thread

import numpy as np
from abc import abstractmethod
from pyedflib import FILETYPE_BDFPLUS, EdfWriter

scale = 2**23
info = {
    "label": "",
    "physical_max": int(round((scale - 1) * 0.02235174)),
    "physical_min": int(round(-scale * 0.02235174)),
    "digital_max": scale - 1,
    "digital_min": -scale,
    "dimension": "uV",
    "sample_frequency": 0,
}


class bdfSaver(EdfWriter, Thread):
    def __init__(self, filename, chs: dict, fs: int, chs_len: int = None) -> None:
        self.fs = int(fs)
        self.chs = [i for i in chs.keys()]
        self.ch_names = [i for i in chs.values()]
        self.filename = filename
        chs_len = len(chs) if chs_len is None else chs_len
        Thread.__init__(self, daemon=True)
        EdfWriter.__init__(self, filename, chs_len, FILETYPE_BDFPLUS)
        self.elapsed_seconds: int = 0
        self._data_position = 0
        self._run_flag = True
        self._data_q = Queue()
        self._halt_flag = Event()
        self._save_cnt = 0
        self._data_write = np.zeros((len(self.chs), self.fs))

    def _log_inter_trigger(self, description, start, duration):
        if duration != -1:
            duration = min((self._data_position - start) / self.fs, duration * self.fs)
        self.writeAnnotation(start, duration, description)

    def write_Annotation(self, marker):
        super().writeAnnotation(self._data_position / self.fs, -1, marker)

    def _init_chs_info(self, dev_type, ch_info, ch_names) -> None:
        self.setEquipment(dev_type)
        self.setPatientName("eCon")
        self.set_number_of_annotation_signals(30)
        infos = []
        for val in ch_names:
            ch_info["label"] = str(val)
            infos.append(ch_info.copy())
        self.setSignalHeaders(infos)

    @abstractmethod
    def write_chunk(self, frames: list):
        pass

    def run(self):
        print("Data Collection Start")
        while self._run_flag:
            self._halt_flag.wait()
            while not self._data_q.empty():
                data_write = self._data_q.get()
                self.writeSamples(data_write, digital=False)
                self.elapsed_seconds += 1
            self._halt_flag.clear()
        self.close()
        print(f"BDF file saved to {self.filename}, {datetime.now()}")

    def close_bdf(self):
        self._run_flag = False
        self._halt_flag.set()
        self.join()


class bdfSaverIRecorder(bdfSaver):
    def __init__(self, filename, chs: dict, fs: int, dev_type: str) -> None:
        super().__init__(filename, chs, fs)
        info_eeg = info.copy()
        info_eeg.update({"sample_frequency": self.fs})
        self._init_chs_info(dev_type, info_eeg, self.ch_names)
        self.start()

    def write_chunk(self, frames: list):
        for frame in frames:
            if frame[-1] > 0:  # trigger box trigger
                self.write_Annotation(f"T{int(frame[-1])}")
            self._data_write[:, self._save_cnt] = frame[:-1]
            self._save_cnt += 1
            self._data_position += 1
            if self._save_cnt == self.fs:
                self._data_q.put(self._data_write.copy())
                self._save_cnt = 0
                self._halt_flag.set()


class bdfSaverEEG(bdfSaver):
    def __init__(self, filename, chs: dict, fs: int, dev_type: str) -> None:
        super().__init__(filename, chs, fs)
        self.chs_len = len(chs)
        info_eeg = info.copy()
        info_eeg.update({"sample_frequency": self.fs})
        self._init_chs_info(dev_type, info_eeg, self.ch_names)
        self.start()

    def write_chunk(self, frames: list):
        # [channel, fs * t]
        # [[ch1_1,ch1_2,...],[ch2_1,ch2_2,...],...]
        for frame in frames:
            eeg_signal = np.array(frame[:-1]).T
            offset = (
                eeg_signal.shape[1]
                if self._save_cnt + eeg_signal.shape[1] <= self.fs
                else self.fs - self._save_cnt
            )
            self._data_write[:, self._save_cnt : self._save_cnt + offset] = eeg_signal[
                :, :offset
            ]
            self._save_cnt += offset
            if self._save_cnt >= self.fs:
                self._data_q.put(np.vsplit(self._data_write, self.chs_len))
                self._save_cnt = 0
                self._halt_flag.set()


class bdfSaverEEGIMU(bdfSaver):
    def __init__(
        self, filename, chs_eeg: dict, fs_eeg: int, chs_imu: dict, fs_imu, dev_type: str
    ) -> None:
        self.fs_eeg = int(fs_eeg)
        self.chs_eeg = [i for i in chs_eeg.keys()]
        self.chs_eeg_len = len(chs_eeg)
        self.fs_imu = fs_imu
        self.chs_imu = [i for i in chs_imu.keys()]
        self.chs_imu_len = len(chs_imu)
        self.chs_eeg_names = [i for i in chs_eeg.values()]
        self.chs_imu_names = [i for i in chs_imu.values()]
        super().__init__(filename, {}, 0, self.chs_eeg_len + self.chs_imu_len)
        if not isinstance(self.fs_imu, int):
            self.setDatarecordDuration(2)
            self.fs_eeg *= 2
            self.fs_imu = int(2 * self.fs_imu)

        info_eeg = info.copy()
        info_eeg.update({"sample_frequency": self.fs_eeg})
        info_imu = info.copy()
        info_imu.update({"sample_frequency": self.fs_imu})
        self.__init_chs_info(
            dev_type, info_eeg, self.chs_eeg_names, info_imu, self.chs_imu_names
        )
        self.__save_cnt_eeg = 0
        self.__save_cnt_imu = 0
        self.__data_write_eeg = np.zeros((self.chs_eeg_len, self.fs_eeg))
        self.__data_write_imu = np.zeros((self.chs_imu_len, self.fs_imu))

        self.start()

    def __init_chs_info(
        self, dev_type, ch_eeg_info, ch_eeg_names, ch_imu_info, ch_imu_names
    ) -> None:
        self.setEquipment(dev_type)
        self.setPatientName("eCon")
        self.set_number_of_annotation_signals(30)
        infos = []
        for val in ch_eeg_names:
            ch_eeg_info["label"] = str(val)
            infos.append(ch_eeg_info.copy())
        for val in ch_imu_names:
            ch_imu_info["label"] = str(val)
            infos.append(ch_imu_info.copy())
        self.setSignalHeaders(infos)

    def write_chunk(self, frames: list):
        # [channel, fs * t]
        # [[ch1_1,ch1_2,...],[ch2_1,ch2_2,...],...[imu1_1,imu1_2,...],[imu2_1,imu2_2,...]]
        for frame in frames:
            eeg_signal = np.array(frame[:-1]).T
            imu_signal = np.array(frame[-1:]).T
            self.__data_write_eeg[
                :, self.__save_cnt_eeg : self.__save_cnt_eeg + eeg_signal.shape[1]
            ] = eeg_signal
            self.__data_write_imu[:, self.__save_cnt_imu : self.__save_cnt_imu + 1] = (
                imu_signal
            )
            self.__save_cnt_eeg += eeg_signal.shape[1]
            self.__save_cnt_imu += 1
            if self.__save_cnt_eeg >= self.fs_eeg or self.__save_cnt_imu >= self.fs_imu:
                self._data_q.put(
                    np.vsplit(self.__data_write_eeg, self.chs_eeg_len)
                    + np.vsplit(self.__data_write_imu, self.chs_imu_len)
                )
                self.__save_cnt_eeg = 0
                self.__save_cnt_imu = 0
                self._halt_flag.set()

    def _log_inter_trigger(self, description, start, duration):
        pass

    def writeAnnotation(
        self, onset_in_seconds, duration_in_seconds, description, str_format="utf_8"
    ):
        pass
