import re


class Parser:
    def __init__(self) -> None:
        self.__buffer = ""
        self.__pattern = re.compile(r"55aa[0-9A-Za-z]{26}00")
        self.bat = 0

    def __cut(self, data, bytes):
        return [data[i : i + bytes] for i in range(0, len(data), bytes)]

    def parse(self, q: bytes):
        self.__buffer += q.hex()
        frame_list = self.__pattern.findall(self.__buffer)
        self.__buffer = self.__pattern.split(self.__buffer)[-1]

        data_list = []
        for frame in frame_list:
            check_sum_str = hex(sum([int(i, 16) for i in self.__cut(frame[4:-4], 2)]))
            if frame[28:30] != check_sum_str[-2:]:
                print("checksum error")
                continue
            d = self.__cut(frame[4:-4], 3)
            dd = [(int(i, 16) - 2048) / 4096 * 3300000 / 2500 for i in d]
            data_list.append(dd)
        if len(frame_list):
            self.bat = int(frame[-4:-2], 16)
        return data_list  # in uV
