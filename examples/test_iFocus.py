from eConEXG import iFocus
import time

# if port not given, it will connect to the first available device
dev = iFocus()
"""Alternatively, one can search devices using the find_devs() method and connect to the desired one."""
# ret=iFocus.find_devs()
# dev=iFocus(ret[0])

dev.start_acquisition_data()
dev.open_lsl_eeg()
dev.open_lsl_imu()
start = time.time()
count = 0

try:
    while True:
        frames = dev.get_data(timeout=0.02)
        for frame in frames:
            # print(frame)
            count += 5
except KeyboardInterrupt:
    pass

print(f"average fs:{count/(time.time()-start)}")

dev.close_dev()
print(">>>test finished<<<")
