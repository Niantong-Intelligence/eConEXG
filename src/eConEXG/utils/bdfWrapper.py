from threading import Event, Thread
from queue import Queue
import numpy as np
from pyedflib import EdfWriter, FILETYPE_BDFPLUS
from datetime import datetime


class bdfSaver(EdfWriter, Thread):
    def __init__(self, filename, chs: dict, fs: int, devtype: str) -> None:
        self.fs = int(fs)
        self.chs = [i for i in chs.keys()]
        self.ch_names = [i for i in chs.values()]
        self.filename = filename
        Thread.__init__(self, daemon=True)
        EdfWriter.__init__(self, filename, len(self.chs), FILETYPE_BDFPLUS)
        self.__init_chs_info(devtype)
        self.elapsed_seconds: int = 0
        self._data_position = 0
        self.__run_flag = True
        self.__data_q = Queue()
        self.__halt_flag = Event()
        self.__save_cnt = 0
        self.__data_write = np.zeros((len(self.chs), self.fs))
        self.start()

    def _log_inter_trigger(self, description, start, duration):
        if duration != -1:
            duration = min((self._data_position - start) / self.fs, duration * self.fs)
        self.writeAnnotation(start, duration, description)

    def write_Annotation(self, marker):
        super().writeAnnotation(self._data_position / self.fs, -1, marker)

    def __init_chs_info(self, devtype) -> None:
        self.setEquipment(devtype)
        self.setPatientName("eCon")
        self.set_number_of_annotation_signals(30)
        scale = 2**23
        info = {
            "label": "",
            "physical_max": int((scale - 1) * 0.02235174),
            "physical_min": int(-scale * 0.02235174),
            "digital_max": scale - 1,
            "digital_min": -scale,
            "dimension": "uV",
            "sample_frequency": self.fs,
        }
        infos = []
        for val in self.ch_names:
            info["label"] = str(val)
            infos.append(info.copy())
        self.setSignalHeaders(infos)

    def write_chuck(self, frames: list):
        for frame in frames:
            if frame[-1] > 0:  # trigger box trigger
                self.write_Annotation(f"T{int(frame[-1])}")
            # update data for plotting
            self.__data_write[:, self.__save_cnt] = frame[:-1]
            self.__save_cnt += 1
            self._data_position += 1
            if self.__save_cnt == self.fs:
                self.__data_q.put(self.__data_write.copy())
                self.__save_cnt = 0
                self.__halt_flag.set()

    def run(self):
        while self.__run_flag:
            self.__halt_flag.wait()
            while not self.__data_q.empty():
                data_write = self.__data_q.get()
                self.writeSamples(data_write, digital=False)
                self.elapsed_seconds += 1
            self.__halt_flag.clear()
        self.close()
        print(f"BDF file saved to {self.filename}, {datetime.now()}")

    def close_bdf(self):
        self.__run_flag = False
        self.__halt_flag.set()
        self.join()
