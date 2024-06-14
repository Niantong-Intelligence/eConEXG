from eConEXG import iRecorder
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PySide6.QtCore import QTimer

dev = iRecorder(dev_type="USB32")
fs = 2000
dev.set_frequency(fs)

# dev.connect_device("iRe-E5C1EF")
"""Alternatively, one can search devices first and connect to the desired one."""
ret = dev.find_devs(duration=1)
print(f"Devs: {ret}")
dev.connect_device(ret[0])
fftLen = fs * 1
signal_scale = 1.0 / 2000
signal = np.zeros(fftLen, dtype=float)

app = QApplication()
app.quitOnLastWindowClosed()
mainWindow = QMainWindow()
mainWindow.setWindowTitle("Spectrum Analyzer")  # Title
mainWindow.resize(800, 300)  # Size
centralWid = QWidget()
mainWindow.setCentralWidget(centralWid)
lay = QVBoxLayout()
centralWid.setLayout(lay)

specWid = pg.PlotWidget(name="spectrum")
specItem = specWid.getPlotItem()
specItem.setMouseEnabled(y=False)  # y軸方向に動かせなくする
specItem.setYRange(0, int(fs / 2))
specItem.setXRange(0, fs / 2, padding=0)
### Axis
specAxis = specItem.getAxis("bottom")
specAxis.setLabel("Frequency [Hz]")
# specAxis.setScale(fs / 2.0 / (fftLen / 2 ))
# hz_interval = 100
# newXAxis = (np.arange(int(fs / 2 / hz_interval)) ) * hz_interval
# oriXAxis = newXAxis / (fs / 2.0 / (fftLen / 2 ))
# specAxis.setTicks([zip(oriXAxis, newXAxis)])
lay.addWidget(specWid)

mainWindow.show()
dev.start_acquisition_data()


def update_data():
    global signal, dev
    newdata = dev.get_data()
    if (len(newdata) > 0) and (len(newdata) < len(signal)):
        newdata = np.array(newdata)[:, 0]
        signal = np.roll(signal, -len(newdata))
        signal[-len(newdata) :] = newdata


def update_plot():
    global signal, fs
    fftspec = np.fft.fft(signal)
    specItem.plot(abs(fftspec[: int(fs / 2)] * signal_scale), clear=True)


timer = QTimer()
timer.timeout.connect(update_data)
timer.timeout.connect(update_plot)
timer.start(20)
app.exec()
