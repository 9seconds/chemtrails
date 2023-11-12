from __future__ import annotations

import abc
import concurrent.futures
import contextlib
import logging
import pathlib
import sys
import threading
import typing as t
import uuid

import psutil

from chemtrails import trails
from chemtrails import utils


if t.TYPE_CHECKING:
    import os

    from chemtrails import types as tt
    from chemtrails.trails import base


__all__ = ("AbstractHub", "ThreadingHub")


LOG = logging.getLogger(__name__)


class AbstractHub(metaclass=abc.ABCMeta):
    oid: uuid.UUID
    event_disabled: threading.Event
    event_closed: threading.Event

    def __init__(self, enabled: bool = True) -> None:
        self.oid = uuid.uuid4()
        self.event_closed = threading.Event()

        self.event_disabled = threading.Event()
        if enabled:
            self.enable()
        else:
            self.disable()

    def enable(self) -> None:
        self.event_disabled.clear()
        LOG.debug("Pool %s has been enabled", self.oid)

    def disable(self) -> None:
        self.event_disabled.set()
        LOG.debug("Pool %s has been disabled", self.oid)

    def take_snapshot(self) -> None:
        if not self.is_working():
            return

        with (proc := psutil.Process()).oneshot():
            snapshot = trails.Snapshot.create(self.oid, proc)

        if self.can_accept_object(snapshot):
            self.send_object(snapshot)

    @contextlib.contextmanager
    def trace(
        self,
        trace_id: t.Optional[tt.TraceID] = None,
        with_snapshot: bool = False,
    ) -> t.Iterator[tt.TraceDict]:
        if not self.is_working():
            return iter(({},))

        if trace_id is None:
            trace_id = utils.get_source_line(2)

        trace = trails.Trace(self.oid, trace_id, with_snapshot=with_snapshot)

        try:
            with trace as rv:
                yield rv
        finally:
            if self.can_accept_object(trace):
                self.send_object(trace)

    def shutdown(self) -> None:
        self.event_closed.set()
        LOG.debug("Hub %s is shutting down", self.oid)

    def is_working(self) -> bool:
        return not (self.event_closed.is_set() or self.event_disabled.is_set())

    def can_accept_object(self, msg: base.Base) -> bool:
        return True

    @abc.abstractmethod
    def send_object(self, msg: base.Base) -> None:
        raise NotImplementedError()


class ThreadingHub(AbstractHub):
    output_dir: pathlib.Path
    worker_pool: concurrent.futures.ThreadPoolExecutor
    semaphore: threading.Semaphore

    def __init__(
        self,
        output_dir: os.PathLike[str] | pathlib.Path,
        enabled: bool = True,
        *,
        in_progress_limit: int = sys.maxsize,
        num_workers: t.Optional[int] = None,
    ) -> None:
        super().__init__(enabled)

        output_dir = pathlib.Path(output_dir)

        if not output_dir.is_dir():
            raise ValueError(f"{output_dir} is not a directory")

        self.output_dir = output_dir
        self.semaphore = threading.BoundedSemaphore(in_progress_limit)
        self.worker_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=num_workers, thread_name_prefix="chemtrails_worker"
        )

    def shutdown(self) -> None:
        super().shutdown()
        self.worker_pool.shutdown()

        LOG.debug("Hub %s has been shut down", self.oid)

    def send_object(self, obj: base.Base) -> None:
        if self.event_closed.is_set():
            LOG.warning(
                "Hub %s has dropped a message %s because it is closing",
                self.oid,
                obj.name,
            )
            return

        if not self.semaphore.acquire(blocking=False):
            LOG.warning(
                "Hub %s has dropped a message %s because of task in "
                "progress limit",
                self.oid,
                obj.name,
            )

        try:
            self.worker_pool.submit(self.process_object, obj)
        except RuntimeError as exc:
            LOG.warning(
                "Hub %s is closing because of worker pool: %s", self.oid, exc
            )
            self.event_closed.set()
            self.semaphore.release()

    def process_object(self, msg: base.Base) -> None:
        try:
            with self.get_object_storage(msg) as fp:
                msg.save_to(fp)
        except Exception as exc:
            LOG.error(
                "Hub %s could not save object %s: %s", self.oid, msg.name, exc
            )
        finally:
            if not self.event_closed.is_set():
                self.semaphore.release()

    def get_object_storage(self, msg: base.Base) -> t.BinaryIO:
        match msg:
            case trails.Trace(trace_id=trace_id, oid=oid):
                return self.output_dir.joinpath(
                    f"{self.oid}_{utils.get_filesystem_safe_name(trace_id)}"
                    f"_{oid}.trace"
                ).open(mode="wb")

            case trails.Snapshot(oid=oid):
                return self.output_dir.joinpath(
                    f"{self.oid}_{oid}.snapshot"
                ).open(mode="wb")

        raise RuntimeError(f"Unknown object {msg.name}")
