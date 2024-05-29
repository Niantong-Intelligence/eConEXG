from pylsl import StreamInfo, StreamOutlet, cf_double64


class lslSender(StreamOutlet):
    def __init__(
        self,
        elctds: dict = {},
        dev="eConEEG",
        devtype="EEG",
        fs=500,
        with_trigger=True,
        precision=cf_double64,
    ):
        info = StreamInfo(
            name=dev,
            type=devtype,
            channel_count=len(elctds) + (1 if with_trigger else 0),  # Trigger
            nominal_srate=fs,
            channel_format=precision,
            source_id=dev,  # important
        )
        maf = "Niantong Intelligence Technology Co., Ltd."
        info.desc().append_child_value("manufacturer", maf)
        chns = info.desc().append_child("channels")
        for label in elctds.values():
            ch = chns.append_child("channel")
            ch.append_child_value("label", label)
            ch.append_child_value("unit", "microvolts")
            ch.append_child_value("type", "EEG")
            ch.append_child_value("scaling_factor", "1")
        # Trigger
        if with_trigger:
            ch = chns.append_child("channel")
            ch.append_child_value("label", "Trigger Box")
            ch.append_child_value("unit", "int")
            ch.append_child_value("type", "Trigger Box")
            ch.append_child_value("scaling_factor", "1")
        super().__init__(info, max_buffered=60)

    def push_chuck(self, frames):
        super().push_chunk(frames)
