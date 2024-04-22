from eConEXG import iRecorder
import time

if __name__ == "__main__":
    dev = iRecorder(dev_type="USB32", fs=2000)
    ret = dev.find_devs(duration=5)
    print(ret)
    dev.connect_device(ret[0])
    # dev.update_channels({0:'aa',1:'bb'})
    print(dev.get_dev_info())
    dev.start_acquisition_data()
    dev.save_bdf_file("test.bdf")
    dev.open_lsl_stream()
    start = time.time()
    first_data = None
    count = 0
    duration = 20
    while time.time() - start < duration:
        frames = dev.get_data(timeout=0.02)
        for frame in frames:
            if not first_data:
                first_data = time.time()
                print(f"First packet delay: {first_data-start}")
            count += 1
    print(f"average fs:{count/(time.time()-first_data)}")

    dev.start_acquisition_impedance()
    start = time.time()
    while time.time() - start < duration:
        print(dev.get_impedance())
        time.sleep(2)

    dev.close_dev()
    print(">>>test finished<<<")
