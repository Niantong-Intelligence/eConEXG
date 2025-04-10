from eConEXG.eConAlpha import eConAlpha
import time

# change sample frequency to 500Hz for new firmware version in class args.
# iFocus._dev_args.update({"fs_eeg": 500,"fs_imu": 100})


# if port not given, it will connect to the first available device
dev = eConAlpha()
print(dev.get_dev_info())

"""Alternatively, one can set the sampling frequency to 500Hz after device initialization, this will not change class args."""
# dev.set_frequency(500)

"""Alternatively, one can search devices using the find_devs() method and connect to the desired one."""
# ret=iFocus.find_devs()
# dev=iFocus(ret[0])

""""Vibrate the arm band, wait for a while after connection before using vibrate functionality"""
time.sleep(1)
dev.shock_band()

dev.start_acquisition_data()
dev.create_bdf_file("test.bdf")
"""Open lsl streams for EEG and IMU data"""
dev.open_lsl_emg()
dev.open_lsl_imu()
dev.open_lsl_emg_imu()

count = 0
first_packet = None
try:
    while True:
        frames = dev.get_data(timeout=0.01)
        for frame in frames:
            if first_packet is None:
                first_packet = time.time()
            print(frame)
            count += 8
except KeyboardInterrupt:
    dev.close_bdf_file()
    pass

if first_packet is not None:
    print(f"average fs:{count/(time.time()-first_packet)}")

"""Close lsl streams for EEG and IMU data"""
dev.close_lsl_emg()
dev.close_lsl_imu()
dev.close_lsl_emg_imu()


try:
    dev.close_dev()
except Exception as e:
    print(e)
print(">>>test finished<<<")
