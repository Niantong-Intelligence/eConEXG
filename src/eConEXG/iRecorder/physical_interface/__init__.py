DEVTYPE = 0


def get_interface(TYPE):
    from platform import system

    global DEVTYPE
    DEVTYPE = TYPE
    if TYPE in ["W8", "W16"]:
        if system() == "Windows":
            from .bt import bt as phy_interface
            from . import bt

            bt.CHANNELS = 8 if TYPE == "W8" else 16
        else:
            raise NotImplementedError("Unsupported platform")

    elif TYPE in ["W32"]:
        if system() == "Windows":
            from .wifi_windows import wifiWindows as phy_interface
        elif system() == "Darwin":
            from .wifi_macos import wifiMACOS as phy_interface
        elif system() == "Linux":
            from .wifi_linux import wifiLinux as phy_interface
        else:
            raise NotImplementedError("Unsupported platform")

    elif TYPE in ["USB32"]:
        from .com import com as phy_interface

    else:
        raise NotImplementedError("Unsupported interface type")

    return phy_interface


def get_sock(TYPE):
    global DEVTYPE
    DEVTYPE = TYPE
    if DEVTYPE in ["W8", "W16"]:
        from .device_socket import bluetooth_socket as sock
    elif DEVTYPE in ["W32"]:
        from .device_socket import wifi_socket as sock

    elif DEVTYPE in ["USB32"]:
        from .device_socket import com_socket as sock
    else:
        raise NotImplementedError("Unsupported socket type")
    return sock
