from __future__ import annotations

import logging
import threading
import typing as t


if t.TYPE_CHECKING:
    from chemtrails import types as tt


LOG = logging.getLogger(__name__)


class Scheduler:
    period: tt.TimeSeconds
    func: t.Callable[[], None]
    timer: threading.Timer
    lock: threading.Lock
    enabled: bool

    def __init__(
        self, period: tt.TimeSeconds, func: t.Callable[[], None]
    ) -> None:
        self.period = period
        self.func = func
        self.timer = threading.Timer(self.period, self.run)
        self.lock = threading.Lock()

    def start(self) -> None:
        self.enabled = True
        self.timer.start()

    def run(self) -> None:
        try:
            self.func()
        except Exception as exc:
            LOG.warning("Failed to execute %s: %s", self.func.__name__, exc)
        else:
            LOG.debug("%s has executed", self.func.__name__)

        with self.lock:
            if self.enabled:
                self.timer = threading.Timer(self.period, self.run)

    def stop(self) -> None:
        with self.lock:
            self.timer.cancel()
            self.enabled = False
