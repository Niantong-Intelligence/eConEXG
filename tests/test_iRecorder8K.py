from eConEXG import iRecorder
import time

dev = iRecorder(dev_type="USB32")
fs = 2000
dev.set_frequency(fs)
print(dev.get_dev_info())
# dev.update_channels({0: "FPz", 1: "Oz", 2: "CPz"})

# dev.connect_device("iRe-E5C1EF")
"""Alternatively, one can search devices first and connect to the desired one."""
ret = dev.find_devs(duration=1)
print(f"Devs: {ret}")
dev.connect_device(ret[0])

dev.start_acquisition_data()
dev.save_bdf_file("test.bdf")
# dev.open_lsl_stream()
start = time.time()
first_data = None
count = 0
duration = 10
try:
    while True:
        frames = dev.get_data(timeout=0.02)
        for frame in frames:
            count += 1
            if count % fs == 0:
                print(f"{count/fs}s")
    print(f"average fs:{count/(time.time()-first_data)}")

    # dev.stop_acquisition()

    dev.start_acquisition_impedance()
    start = time.time()
    while time.time() - start < duration:
        print(f"Impedance: {dev.get_impedance()}")
        time.sleep(2)
except KeyboardInterrupt:
    print(f"total data:{count}")

dev.close_dev()
print(">>>test finished<<<")
