from eConEXG import iRecorder


if __name__ == '__main__':
    dev=iRecorder(dev_type='W16')
    # dev.find_device()
    dev.connect_device("88:6B:0F:8A:64:69")
    dev.join()