from eConEXG import triggerBoxWireless
import time

# data unit in seconds
INTERVAL = 0.05  # marker interval
DURATION = 100  # None for infinite loop

dev = triggerBoxWireless()

_count = 0
_elapsed = 0
_start = time.perf_counter()
try:
    while True:
        if time.perf_counter() - _start < _elapsed:
            continue
        dev.sendMarker(1)
        _elapsed += INTERVAL
        _count += 1
        if time.perf_counter() - _start > DURATION:
            break
except KeyboardInterrupt:
    dev.close_dev()
except Exception as e:
    print(e)
finally:
    print(f"\n>>>Total Markers: {_count}<<<")
