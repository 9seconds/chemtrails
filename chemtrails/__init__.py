import atexit
import contextlib
import functools
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
    "traced",
    "AbstractHub",
    "Snapshot",
    "ThreadingHub",
    "Trace",
)


P = t.ParamSpec("P")  # noqa: VNE001
T = t.TypeVar("T")


Hub = ThreadingHub(pathlib.Path(""), False)
atexit.register(lambda: Hub.shutdown())


def configure_default_hub(
    output_dir: pathlib.Path,
    *,
    in_progress_limit: int = sys.maxsize,
    num_workers: int | None = None,
) -> None:
    global Hub

    Hub.shutdown()
    Hub = ThreadingHub(
        output_dir,
        True,
        in_progress_limit=in_progress_limit,
        num_workers=num_workers,
    )


def enable() -> None:
    Hub.enable()


def disable() -> None:
    Hub.disable()


def take_snapshot() -> None:
    Hub.take_snapshot()


def traced(
    trace_id: t.Optional[tt.TraceID] = None, with_snapshot: bool = False
) -> t.Callable[[t.Callable[P, T]], t.Callable[P, T]]:
    def outer_decorator(func: t.Callable[P, T]) -> t.Callable[P, T]:
        trace_id_ = trace_id if trace_id is not None else func.__name__

        @functools.wraps(func)
        def inner_decorator(*args: P.args, **kwargs: P.kwargs) -> T:
            with trace(trace_id_, with_snapshot):
                return func(*args, **kwargs)

        return inner_decorator

    return outer_decorator


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
