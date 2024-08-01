from eConEXG import triggerBoxWired
import time

# data unit in seconds
INTERVAL = 0.05  # marker interval
DURATION = 3000  # None for infinite loop

dev = triggerBoxWired()

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
        if DURATION is None:
            continue
        if time.perf_counter() - _start > DURATION:
            break
except KeyboardInterrupt:
    pass
except Exception as e:
    print(e)
finally:
    print(f"\n>>>Total Markers: {_count}<<<")

try:
    dev.close_dev()
except Exception:
    pass
