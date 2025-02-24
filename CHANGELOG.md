# Changelog

This file contains tracks the changes landing in eConEXG. 
<!-- released start -->

### 0.1.30

* **Add** iSense USB SDK to the repository

### 0.1.20

* **Fix** bug where multiple devices of different type cannot be connected simultaneously
* **Fix** bug where LSL stream cannot simultaneously transmit EMG and IMU data
* **Add** a new data transmitted policy. data passed directly without through queue, which is more efficient

## 0.1.18

Release on 2024-10-10

* **ADD** Add `create_bdf_file` and `close_bdf_file` to iRecorder and eConAlpha. 
* **ADD** Add imu support to iRecorder and eConAlpha. 

## 0.1.15

* **ADD** eConAlpha device SDK
 
## 0.1.14

Released on 2024-08-08.

<!-- * **Add** `set_callback_handler()` method in `iRecorder` to allow user-defined callback function to be called when device connection lost. -->

* **Update** pyEDFlib dependency requirement in `pyproject.toml` from `0.1.37` to `0.1.38` to support `numpy>=2.0.0`.
* **Optimize** `set_frequency()` in `iRecorder`, now you can set sample rate after device connection.

---

* **Fix** `iFocus` not raise Exception after lost connection with USBadapter.
* **Change** `with_q` argument in `iRecorder` and `iFocus` from constructor to `start_acquisition_data()`.
* **Deprecate** `save_bdf_file()` in `iRecorder`, use `create_bdf_file()` instead.

## 0.1.13

Released on 2024-08-01.

* **Add** `get_dev_info()` in `iFocus` class to get device information.
* **Add** selectable `500Hz` eeg and corresponding `100Hz` IMU sampling rate in `iFocus` class through `set_frequency()`.
* **Add** `with_q = False` option in `iRecorder` and `iFocus` constructor to drop the necessity of loop calling `get_data()` in SIGNAL mode.
* **Add** `__version__` field of eConEXG package to check the package version, it can be accessed throught `eConEXG.__version__`.

---

* **Fix**  last valid packet number in `iFocus` warning message wrongly displayed as a fixed number issue.
* **Change** the default data parse length from 0.01 seconds to 10 frames in `iRecorder` to match hardware settings.
* **Improve** the aesthetics of a document interface.

## 0.1.12

Released on 2024-07-25.

---

* **Fix** equipment format warning issue on bdf save.
* **Fix** Rounding physical_max value of bdf file，resulting to more accurate data precision.
* **Fix** `sendMarker()` function not working in `triggerBox` class when python version<3.11.

## 0.1.11

Released on 2024-07-12.

---

* **Update** documentation homepage.

## 0.1.10

Released on 2024-07-08.

* **Add** lsl support for iFocus. 
* **Add** support for iRecorder 16-channel wired mode.

---

* **Change** default timeout of `get_data()` function in `iRecorder` from `None` to `0.02`.

## 0.1.09

Released on 2024-06-28.

* **Add** support for iRecorder 8-channel wired mode.

---


