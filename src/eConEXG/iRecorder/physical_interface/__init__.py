
__all__ = ["com_util", "bluetooth_util", "wifi_util"]
import platform

from . import com as com_util

system = platform.system()
if system == "Windows":
    from . import bluetooth as bluetooth_util
    from . import wifi_windows as wifi_util
elif system == "Linux":
    from . import bluetooth as bluetooth_util
    from . import wifi_windows as wifi_util
elif system == "Darwin":
    from . import wifi_macos as wifi_util
