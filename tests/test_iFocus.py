from eConEXG import iFocus
import time

if __name__ == "__main__":
    # if port not given, it will connect to the first available device
    dev = iFocus()
    """Alternatively, one can search devices using the find_devs() method and connect to the desired one."""
    # ret=iFocus.find_devs()
    # dev=iFocus(ret[0])

    dev.start_acquisition_data()
    start = time.time()
    count = 0
    while True:
        try:
            frames = dev.get_data(timeout=0.02)
            for frame in frames:
                # print(frame)
                count += 5
        except KeyboardInterrupt:
            break

    print(f"average fs:{count/(time.time()-start)}")

    dev.close_dev()
    print(">>>test finished<<<")
