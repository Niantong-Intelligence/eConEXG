from eConEXG import iRecorder
import time

dev = iRecorder(dev_type="USB8")

"""query and set frequency, optional, if not set, the lowest available frequency will be used."""
# print(dev.get_available_frequency())
# dev.set_frequency(500)

print(dev.get_dev_info())

"""query available devices continously"""
# dev.find_devs()
# # `do other things`
# available_devs = []
# while True:
#     available_devs.extend(dev.get_devs())
# #     `connect to the desired one`
dev.find_devs()
while True:
    ret = dev.get_devs()
    if ret:
        break

"""Alternatively, one can query available devices in block mode and connect to the desired one."""
# ret = dev.find_devs(duration=5)
print(f"Devs: {ret}")
"""Also, one can directly connect to the desired device by its name without calling `find_devs` first."""
dev.connect_device(ret[0])

"""Acquire data."""
dev.start_acquisition_data(with_q=True)

"""Create BDF file and open LSL stream."""
# dev.create_bdf_file("test.bdf")
# dev.open_lsl_stream()
start = time.time()
first_data = None
count = 0
duration = 10
while time.time() - start < duration:
    frames = dev.get_data(timeout=0.01)
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
