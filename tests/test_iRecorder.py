from eConEXG import iRecorder
import time

dev = iRecorder(dev_type="USB32")
print(dev.get_dev_info())


"""query and set frequency, optional, if not set, the lowest available frequency will be used."""
# print(dev.get_available_frequency())
# dev.set_frequency(1000)



"""query available devices continously"""
# dev.find_devs()
# # `do other things`
# available_devs = []
# while True:
#     available_devs.extend(dev.get_devs())
# #     `connect to the desired one`
    

"""Alternatively, one can query available devices in block mode and connect to the desired one."""
ret = dev.find_devs(duration=5)
print(f"Devs: {ret}")
dev.connect_device(ret[0])

dev.start_acquisition_data()
# dev.save_bdf_file("test.bdf")
# dev.open_lsl_stream()
start = time.time()
first_data = None
count = 0
duration = 10
try:
    while time.time() - start < duration:
        frames = dev.get_data(timeout=0.02)
        for frame in frames:
            if not first_data:
                first_data = time.time()
                print(f"First packet delay: {first_data-start}")
            count += 1
    print(f"average fs:{count/(time.time()-first_data)}")

    # dev.stop_acquisition()

    dev.start_acquisition_impedance()
    start = time.time()
    while time.time() - start < duration:
        print(f"Impedance: {dev.get_impedance()}")
        time.sleep(2)
except KeyboardInterrupt:
    pass

dev.close_dev()
print(">>>test finished<<<")
