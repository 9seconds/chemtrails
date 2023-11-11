import atexit
import contextlib
import pathlib
import sys
import typing as t

from chemtrails import types as tt
from chemtrails import utils
from chemtrails.hub import AbstractHub
from chemtrails.hub import Scheduler
from chemtrails.hub import ThreadingHub
from chemtrails.trails import Snapshot
from chemtrails.trails import Trace
from chemtrails.trails import sniff


__all__ = (
    "configure_default_hub",
    "sniff",
    "enable",
    "disable",
    "take_snapshot",
    "take_snapshot_each",
    "trace",
    "AbstractHub",
    "Snapshot",
    "ThreadingHub",
    "Trace",
)


Hub = ThreadingHub(pathlib.Path(""), False)
atexit.register(lambda: Hub.shutdown())


def configure_default_hub(
    output_dir: pathlib.Path,
    *,
    max_size: int = sys.maxsize,
    num_workers: int | None = None,
) -> None:
    global Hub

    Hub.shutdown()
    Hub = ThreadingHub(
        output_dir, True, max_size=max_size, num_workers=num_workers
    )


def enable() -> None:
    Hub.enable()


def disable() -> None:
    Hub.disable()


def take_snapshot() -> None:
    Hub.take_snapshot()


def trace(
    trace_id: t.Optional[tt.TraceID] = None, with_snapshot: bool = False
) -> contextlib.AbstractContextManager[tt.TraceDict]:
    if trace_id is None:
        trace_id = utils.get_source_line(3)

    return Hub.trace(trace_id, with_snapshot)


def take_snapshot_each(period: tt.TimeSeconds) -> t.Callable[[], None]:
    scheduler = Scheduler(period, take_snapshot)
    scheduler.start()

    return scheduler.stop
