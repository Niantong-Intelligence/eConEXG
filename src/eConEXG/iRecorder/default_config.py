def getChannels(channels: int):
    if channels == 8:
        return CH8
    elif channels == 16:
        return CH16
    elif channels == 32:
        return CH32


CH8 = {
    0: "FCz",
    1: "TP9",
    2: "Pz",
    3: "POz",
    4: "O1",
    5: "Oz",
    6: "O2",
    7: "TP10",
}
CH16 = {
    0: "Fp1",
    1: "Fp2",
    2: "F3",
    3: "Fz",
    4: "F4",
    5: "T7",
    6: "C3",
    7: "Cz",
    8: "C4",
    9: "T8",
    10: "P3",
    11: "Pz",
    12: "P4",
    13: "O1",
    14: "Oz",
    15: "O2",
}
CH32 = {
    0: "Fp1",
    1: "AF3",
    2: "F7",
    3: "F3",
    4: "FC1",
    5: "FC5",
    6: "T7",
    7: "C3",
    8: "Cz",
    9: "FC2",
    10: "FC6",
    11: "F8",
    12: "F4",
    13: "Fz",
    14: "AF4",
    15: "Fp2",
    16: "O2",
    17: "PO4",
    18: "P4",
    19: "P8",
    20: "CP6",
    21: "CP2",
    22: "C4",
    23: "T8",
    24: "CP5",
    25: "CP1",
    26: "Pz",
    27: "P3",
    28: "P7",
    29: "PO3",
    30: "O1",
    31: "Oz",
}
