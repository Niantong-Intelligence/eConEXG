import time


class wifi_socket:
    def __init__(self, sock_args, retry_timeout=5) -> None:
        from socket import socket, AF_INET, SOCK_STREAM

        self.__sock_args = sock_args
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.settimeout(retry_timeout)
        self.__socket.connect(self.__sock_args["sock"])
        time.sleep(0.1)
        self.__socket.settimeout(5)

    def close_socket(self):
        try:
            self.__socket.shutdown(2)
        finally:
            self.__socket.close()
            self.__socket = None

    def start_impe(self):
        self.__socket.send(b"Z")

    def start_data(self):
        self.__socket.send(b"W")

    def recv_socket(self, buffersize: int = 2048):
        return self.__socket.recv(buffersize)

    def stop_recv(self):
        self.__socket.send(b"R")

    def send_heartbeat(self):
        self.__socket.send(b"B")
        bettery = int.from_bytes(self.recv_socket(1), byteorder="big")
        return bettery


class bluetooth_socket:
    def __init__(self, sock_args) -> None:
        from socket import AF_BLUETOOTH, socket, SOCK_STREAM, BTPROTO_RFCOMM

        self.delay = 0.2
        self.__sock_args = sock_args
        self.__socket = socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)
        self.__socket.connect(self.__sock_args["sock"])
        self.__socket.settimeout(5)

    def close_socket(self):
        self.__socket.close()
        time.sleep(self.delay)
        self.__socket = None

    def start_impe(self):
        self.__socket.send(b"Z")
        time.sleep(self.delay)

    def start_data(self):
        self.__socket.send(b"W")
        time.sleep(self.delay)

    def recv_socket(self, buffersize: int = 550):
        return self.__socket.recv(buffersize)

    def stop_recv(self):
        self.__socket.send(b"R")
        time.sleep(self.delay)

    def send_heartbeat(self):
        self.__socket.send(b"B")
        time.sleep(self.delay)
        bettery = int.from_bytes(self.recv_socket(1), byteorder="big")
        return bettery


class com_socket:
    order = {
        500: b"\x55\x66\x52\x41\x54\x45\x01\x0a",
        1000: b"\x55\x66\x52\x41\x54\x45\x02\x0a",
        2000: b"\x55\x66\x52\x41\x54\x45\x03\x0a",
        4000: b"\x55\x66\x52\x41\x54\x45\x04\x0a",
        8000: b"\x55\x66\x52\x41\x54\x45\x05\x0a",
        "W": b"\x55\x66\x4d\x4f\x44\x45\x57\x0a",
        "Z": b"\x55\x66\x4d\x4f\x44\x45\x5a\x0a",
        "R": b"\x55\x66\x4d\x4f\x44\x45\x52\x0a",
        "B": b"\x55\x66\x42\x41\x54\x54\x42\x0a",
        "close": b"\x55\x66\x44\x49\x53\x43\x01\x0a",
    }

    def __init__(self, sock_args) -> None:
        from serial import Serial

        self.command_wait = 0.05
        self.__sock_args = sock_args
        self.__socket = Serial(timeout=5)
        self.__socket.port = self.__sock_args["sock"]
        self.__socket.open()
        self.__socket.write(self.order[self.__sock_args["fs"]])
        time.sleep(self.command_wait)
        self.__socket.read_all()

    def close_socket(self):
        self.__socket.write(self.order["R"])
        # self.__socket.write(self.order['close'])
        time.sleep(self.command_wait)
        self.__socket.read_all()
        self.__socket.close()
        self.__socket = None

    def start_impe(self):
        ack = self.__socket.write(self.order["Z"])
        self.__socket.read(ack)

    def start_data(self):
        ack = self.__socket.write(self.order["W"])
        self.__socket.read(ack)

    def recv_socket(self, buffersize: int = 1020):
        return self.__socket.read(buffersize)

    def stop_recv(self):
        self.__socket.write(self.order["R"])
        time.sleep(self.command_wait)
        self.__socket.read_all()

    def send_heartbeat(self):
        ack = self.__socket.write(self.order["B"])
        ret = self.__socket.read(ack + 1)
        battery = ret[-1]
        return battery
