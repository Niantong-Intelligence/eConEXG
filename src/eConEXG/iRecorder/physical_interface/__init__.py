def get_interface(dev_type, queue):
    from platform import system

    if dev_type in ["W8", "W16"]:
        if system() == "Windows":
            from .bt import bt

            return bt(dev_type, queue)
        else:
            raise NotImplementedError("Unsupported platform")

    elif dev_type in ["W32"]:
        if system() == "Windows":
            from .wifi_windows import wifiWindows as wifiInterface
        elif system() == "Darwin":
            from .wifi_macos import wifiMACOS as wifiInterface
        elif system() == "Linux":
            from .wifi_linux import wifiLinux as wifiInterface
        else:
            raise NotImplementedError("Unsupported platform")
        return wifiInterface(queue)

    elif "USB" in dev_type:
        from .com import com

        return com(dev_type, queue)
    else:
        raise NotImplementedError("Unsupported interface type")


def get_sock(TYPE):
    if TYPE in ["W8", "W16"]:
        from .device_socket import bluetooth_socket as sock
    elif TYPE in ["W32"]:
        from .device_socket import wifi_socket as sock
    elif "USB" in TYPE:
        from .device_socket import com_socket as sock
    else:
        raise NotImplementedError("Unsupported socket type")
    return sock
