import platform
from . import com as com_util
from . import virtual_interface as vir_util

system = platform.system().lower()

if system == "windows":
    from . import bluetooth as bluetooth_util
    from . import wifi_windows as wifi_util
elif system == "linux":
    from . import bluetooth as bluetooth_util
    from . import wifi_windows as wifi_util
else:
    from . import wifi_macos as wifi_util
