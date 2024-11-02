from pylsl import StreamInfo, StreamOutlet, cf_double64


class lslSender(StreamOutlet):
    def __init__(
            self,
            elctds: dict = {},
            dev="eConEEG",
            devtype="EEG",
            fs=500,
            with_trigger=True,
            unit="microvolts",
            precision=cf_double64,
    ):
        info = StreamInfo(
            name=dev,
            type=devtype,
            channel_count=len(elctds) + (1 if with_trigger else 0),  # Trigger
            nominal_srate=fs,
            channel_format=precision,
            source_id=dev,
        )
        maf = "Niantong Intelligence Technology Co., Ltd."
        info.desc().append_child_value("manufacturer", maf)
        chns = info.desc().append_child("channels")
        for label in elctds.values():
            ch = chns.append_child("channel")
            ch.append_child_value("label", label)
            ch.append_child_value("unit", unit)
            ch.append_child_value("type", devtype)
            ch.append_child_value("scaling_factor", "1")
        # Trigger
        if with_trigger:
            ch = chns.append_child("channel")
            ch.append_child_value("label", "Trigger Box")
            ch.append_child_value("unit", "int")
            ch.append_child_value("type", "Trigger Box")
            ch.append_child_value("scaling_factor", "1")
        super().__init__(info, max_buffered=60)


if __name__ == "__main__":
    # test
    lsl_stream = lslSender(
        {0: 'CH0', 1: 'CH1', 2: 'CH2', 3: 'CH3'},
        f"iRe32-000000000",
        "EEG",
        2000,  # 有线2k，无线500
        with_trigger=True,
    )
    """
    数据解析后的格式为[[CH0_0, CH1_0, CH2_0, CH3_0，..., Trigger], [CH0_1, CH1_1, CH2_1, CH3_1, ..., Trigger], ... [CH0_N, CH1_N, CH2_N, CH3_N, ..., Trigger]]
    """
    ret = [[1, 2, 3, 4, 0], [1, 2, 3, 4, 0], [1, 2, 3, 4, 0]]
    lsl_stream.push_chunk(ret)
