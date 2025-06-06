"""
iRecorder SDK Tutorial
"""

"""
install the SDK package:
pip install econexg 
"""

"""
总体流程:
1. 创建对象，并传递采样率参数
3. 查找可用设备
4. 连接目标设备
5. 设备开始获取数据，并将数据存储在队列中，用户再从队列中获取数据
"""


if __name__ == "__main__":
    from eConEXG import iSense
    import time

    """
    创建iSense对象，设置采样率为8000。
    可选采样率有：[250, 500, 1000, 2000, 4000, 8000, 16000]，非法采样率会产生ValueError。
    对象创建后，程序即会自动连接设备，未连接成功会抛出异常。
    """
    dev = iSense(8000)

    """
    使用 start_acquisition_data() 方法将程序状态更改为为数据获取状态。该状态下，程序将循环获取数据。
    """
    dev.start_acquisition_data()
    print("start acquisition")

    """
    使用 data = get_data(timeout) 方法从队列中获取数据。timeout为最长等待时间。
    如将timeout设置为0.1时，若程序在0.1s内未获取任何数据，则自动中断。
    """

    start = time.time()
    duartion = 3
    while time.time() - start < duartion:
        data = dev.get_data()
        # if data.size:
        #     # print(data.shape)

    """
    使用 stop_acquisition() 方法将程序状态设置为停止收集状态，此时程序不再接收数据。
    """
    dev.stop_acquisition()

    """
    使用 start_acquisition_impedance() 方法将程序的状态设置为获取各通道阻抗的状态。
    搭配方法 get_impedance() 方法，获取各通道的具体阻抗。
    """
    dev.start_acquisition_impedance()
    print("start impedance")
    start = time.time()
    while time.time() - start < duartion:
        imp = dev.get_impedance()
        print(imp)

    """
    使用 close_dev() 方法断开设备连接
    """
    dev.close_dev()
    print("finished")
