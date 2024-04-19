from eConEXG import iRecorder
import time

if __name__ == "__main__":
    dev = iRecorder(dev_type="W16")
    # ret=dev.find_devs(duration=5)
    # print(ret)
    dev.connect_device("88:6B:0F:8A:64:69")
    dev.start_acquisition_data()
    start = time.time()
    first_data = None
    count = 0
    duration = 10
    while time.time() - start < duration:
        frames = dev.get_data(timeout=0.02)
        for frame in frames:
            if not first_data:
                first_data = time.time()
                print(f'delay:{first_data-start}')
            count += 1
    print(f"average fs:{count/(time.time()-first_data)}")
    dev.close_dev()
