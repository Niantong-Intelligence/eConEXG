from eConEXG import triggerBoxWireless
import time

if __name__ == "__main__":
    # if port not given, it will connect to the first available device
    dev = triggerBoxWireless()
    """Alternatively, one can search devices using the find_devs() method and connect to the desired one."""

    while True:
        try:
            dev.sendMarker(1)
            time.sleep(0.1)
            print('triggered')
        except KeyboardInterrupt:
            break
    dev.close_dev()
    print(">>>test finished<<<")