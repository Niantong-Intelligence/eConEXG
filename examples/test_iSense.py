from eConEXG import iSense
import time


if __name__ == "__main__":
    dev = iSense(8000)
    start = time.time()
    duartion = 3
    dev.start_acquisition_data()
    print("start acquisition")
    while time.time() - start < duartion:
        data = dev.get_data()
        # if data.size:
        #     # print(data.shape)
    dev.stop_acquisition()
    dev.start_acquisition_impedance()
    print("start impedance")
    start = time.time()
    while time.time() - start < duartion:
        imp = dev.get_impedance()
        print(imp)
    dev.close_dev()
    print("finished")
