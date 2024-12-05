import numpy as np


class NPQueue:
    def __init__(self,  ch_len: int = 32, data_len: int = 8000 * 60):
        self.__array = np.zeros((data_len, ch_len), dtype=np.float64)
        self.__data_len = data_len
        self.__ch_len = ch_len
        self.__cur = 0

    def empty(self):
        return self.__cur == 0

    def get(self):
        data = self.__array[:self.__cur, :]
        self.__cur = 0
        return data

    def put(self, data):
        while self.__cur + len(data) >= self.__data_len:
            cut = int(self.__cur * 0.8)
            self.__array[:cut, :] = data[cut:, :]
            self.__cur = cut
        self.__array[self.__cur:self.__cur + len(data), :] = data[:, :]
        self.__cur += len(data)

