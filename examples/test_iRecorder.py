"""
iRecorder SDK Tutorial
"""

"""
install the SDK package:
pip install econexg 
"""

"""
总体流程:
1. 创建对象
2. 设置采样频率
3. 查找可用设备
4. 连接目标设备
5. 设备开始获取数据，并将数据存储在队列中，用户再从队列中获取数据
"""

if __name__ == "__main__":
    from eConEXG import iRecorder

    import time
    import numpy as np

    """
    iRecorder类在创建对象时只接受一个字符串作为唯一参数，该参数为设备类型。
    目前支持的设备类型有："W8", "USB8", "W16", "USB16", "W32", "USB32"。
    使用 get_dev_info() 方法查看设备的基本信息。
    """
    dev_type = "W32"
    dev = iRecorder(dev_type=dev_type)
    print(dev.get_dev_info())

    """
    设备的默认采样率为500HZ，可使用 set_frequency(num) 方法更改设备的采样率。
    不同类型设备支持的采样率有所不同，使用 get_available_frequency(device_type) 方法查看 device_type 类型的设备所支持的采样频率。
    """
    print(iRecorder.get_available_frequency(dev_type=dev_type))
    dev.set_frequency(500)

    """
    使用 find_devs() 方法进行一次设备检索，检索到的所有可连接设备的地址将被存入到一个队列中。
        注：使用该方法后，程序将一直运行直到找到至少一个可用设备。
    使用 get_devs() 方法获取队列中所有可连接的设备地址，该方法将返回一个存储所有设备地址的列表
    find_devs() 方法搭配 while 循环，让程序持续检索附近可连接的设备。
    """
    dev.find_devs()
    while True:
        ret = dev.get_devs()
        if ret:
            break
    print(f"Devs: {ret}")

    """
    使用 connect_device(device_address) 方法连接目标设备。
    如果已知设备地址，亦可跳过设备检索步骤，直接进行连接。
    iRecorder继承了Thread类，其线程对象再成功连接后，将自行启动。
    """
    dev.connect_device(ret[0])
    # dev.connect_device('iRe-E4A793')

    """
    使用 start_acquisition_data(with_q=True) 方法将程序状态更改为为数据获取状态。该状态下，程序将循环获取数据。
    参数 with_q 设置为 True （默认） 意为获取的数据会被存储到队列中，之后可使用 get_data() 方法从队列中获取数据。
    """
    dev.start_acquisition_data(with_q=True)

    """
    使用 create_bdf_file(file_path) 方法创建bdf文件，后续程序获取的数据将被存入到该bdf文件中。
    搭配 close_bdf_file() 方法，该方法让程序停止将数据存入到bdf文件中。
    """
    # dev.create_bdf_file("test.bdf")
    """
    使用 open_lsl_stream() 方法将数据流发送到实验室数据流协议层上。
    """
    # dev.open_lsl_stream()

    """
    使用 data = get_data(timeout) 方法从队列中获取数据。timeout为最长等待时间。
    如将timeout设置为0.1时，若程序在0.1s内未获取任何数据，则自动中断。
    data的形状为(10, 33)，在队列为空时，data为None。
    一个数据帧Frame的长度为32，前32个分别对应32个通道，最后一个位置（三字节）是电量，校验和，trigger的字节组合（每个一字节）。
    一个data包含10个数据帧。
    """
    start = time.time()
    first_data = None
    count = 0
    duration = 1  # 持续收集数据1s
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
                print(f"First packet delay: {first_data - start}")
            count += 1
    print(f"average fs:{count / (time.time() - first_data)}")

    """
    使用 stop_acquisition() 方法将程序状态设置为停止收集状态，此时程序不再接收数据。
    """
    dev.stop_acquisition()

    """
    使用 start_acquisition_impedance() 方法将程序的状态设置为获取各通道阻抗的状态。
    搭配方法 get_impedance() 方法，获取各通道的具体阻抗。
    """
    dev.start_acquisition_impedance()
    start = time.time()
    while time.time() - start < duration:
        print(f"Impedance: {dev.get_impedance()}")
        time.sleep(2)

    """
    使用 close_dev() 方法断开设备连接
    """
    dev.close_dev()
    print(">>>test finished<<<")

    """
    一些其他方法：
    get_battery_value() 获取电池剩余电量。
    update_channels(channels: Optional[dict] = None) 方法可以指定获取哪些通道的数据。
    如，使用 update_channels({0: "FPz", 1: "Oz", 2: "CPz"}) 后，使用get_data()后获取的数据格式为：
    （10，[FPz, Oz, CPz, 其他]）即 （10，4）
    """
