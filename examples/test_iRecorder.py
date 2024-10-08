from eConEXG import iRecorder
import time
import numpy as np

dev_type = "USB32"
dev = iRecorder(dev_type=dev_type)
print(dev.get_dev_info())

"""query and set frequency, optional, if not set, the lowest available frequency will be used."""
# print(iRecorder.get_available_frequency(dev_type))
# dev.set_frequency(500)


"""query available devices asynchronously """
# dev.find_devs()
# """Open another thread to query available devices"""
# available_devs = []
# while True:
#     available_devs.extend(dev.get_devs())
#     """break and connect to the desired one"""

"""Alternatively, one can query available devices in block mode and connect to the desired one."""
# ret = dev.find_devs(duration=5)

dev.find_devs()
while True:
    ret = dev.get_devs()
    if ret:
        break
print(f"Devs: {ret}")
dev.connect_device(ret[0])

"""Also, one can directly connect to the desired device by its name without calling `find_devs` first."""
# dev.connect_device('iRe-E4A793')
"""Acquire data."""
dev.start_acquisition_data(with_q=True)

"""Create BDF file and open LSL stream."""
# dev.create_bdf_file("test.bdf")
# dev.open_lsl_stream()
start = time.time()
first_data = None
count = 0
duration = 5
while time.time() - start < duration:
    frames = dev.get_data(timeout=0.01)
    print("-------FRAMES-----------")
    try:
        print(len(frames))
        print(len(frames[0]))
        print(len(frames[-1]))
        n = np.array(frames)
        print(n.shape)
    except Exception as e:
        continue
    for frame in frames:
        if not first_data:
            first_data = time.time()
            print(f"First packet delay: {first_data-start}")
        count += 1
print(f"average fs:{count/(time.time()-first_data)}")

"""Stop acquisition, optional."""
# dev.stop_acquisition()
"""Acquire impedance."""
dev.start_acquisition_impedance()
start = time.time()
while time.time() - start < duration:
    print(f"Impedance: {dev.get_impedance()}")
    time.sleep(2)


dev.close_dev()
print(">>>test finished<<<")
