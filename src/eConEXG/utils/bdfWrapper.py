from threading import Event,Thread
from queue import Queue
import numpy as np
from pyedflib import EdfWriter, FILETYPE_BDFPLUS


class bdfSaver(EdfWriter, Thread):

    def __init__(self, filename, chs: dict, fs) -> None:
        self.fs = fs
        self.chs = [i for i in chs.keys()]
        self.ch_names = [i for i in chs.values()]
        EdfWriter.__init__(self, filename, len(self.chs), FILETYPE_BDFPLUS)
        self.__init_chs_info()
        self.elapsed_seconds: int = 0
        self.run_flag = True
        self.data_q = Queue()
        self.halt_flag = Event()
        self.save_cnt = 0
        self.data_position = 0
        self.data_write = np.zeros((len(self.chs), self.fs))
        self.start()

    def _log_inter_trigger(self, description, start, duration):
        if duration != -1:
            duration = min((self.data_position - start) / self.fs, duration * self.fs)
        self.writeAnnotation(start, duration, description)

    def write_Annotation(self, marker):
        super().writeAnnotation(self.data_position / self.fs, -1, marker)

    def __init_chs_info(self) -> None:
        self.setEquipment("iRecorder")
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

    def write_data(self, frames: list[list]):
        self.data_q.put(frames)
        self.halt_flag.set()

    def run(self):
        while self.run_flag:
            self.halt_flag.wait()
            while not self.data_q.empty():
                frames = self.data_q.get()
                for frame in frames:
                    if frame[-1] > 0:  # trigger box trigger
                        self.write_Annotation(f"T{int(frame[-1])}")
                    # update data for plotting
                    self.data_write[:, self.save_cnt] = frame[:-1]
                    self.save_cnt += 1
                    self.data_position += 1
                    if self.save_cnt == self.fs:
                        self.save_cnt = 0
                        self.writeSamples(self.data_write, digital=False)
                        self.elapsed_seconds += 1
            self.halt_flag.clear()
        self.close()
        print("data save succeeded.")

    def close_file(self):
        self.run_flag = False
        self.halt_flag.set()
        self.join()
