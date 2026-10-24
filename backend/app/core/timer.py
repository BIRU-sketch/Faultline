import time
from typing import Optional


class LatencyTimer:
    """
    High-resolution monotonic timer using time.perf_counter().
    Distinguishes an unmeasured/missing state (None) from an actual measured zero.
    """

    def __init__(self):
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> "LatencyTimer":
        self._start_time = time.perf_counter()
        self._end_time = None
        return self

    def stop(self) -> float:
        if self._start_time is None:
            raise RuntimeError("Timer was never started.")
        self._end_time = time.perf_counter()
        return self.elapsed_ms()

    def elapsed_ms(self) -> Optional[float]:
        if self._start_time is None:
            return None
        current = self._end_time if self._end_time is not None else time.perf_counter()
        return round((current - self._start_time) * 1000.0, 2)

    def elapsed_seconds(self) -> Optional[float]:
        ms = self.elapsed_ms()
        return round(ms / 1000.0, 3) if ms is not None else None

    def __enter__(self) -> "LatencyTimer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
