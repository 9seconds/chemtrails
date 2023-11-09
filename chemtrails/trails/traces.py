from __future__ import annotations

import dataclasses
import time
import typing as t
import weakref

import psutil

from chemtrails.trails import base
from chemtrails.trails import snapshots


if t.TYPE_CHECKING:
    import types as stdtypes

    from chemtrails import types as tt


class TraceDict(dict[t.Hashable, t.Any]):
    pass


@dataclasses.dataclass()
class Trace(base.Base):
    trace_id: str

    old_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    new_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    elapsed_ns_perf: tt.TimeNanoseconds = dataclasses.field(
        init=False, default=0
    )
    elapsed_ns_process: tt.TimeNanoseconds = dataclasses.field(
        init=False, default=0
    )
    user: TraceDict = dataclasses.field(init=False, default_factory=TraceDict)

    @property
    def class_metadata(self) -> tt.ClassMetadata:
        return {
            "trace_id": self.trace_id,
        }

    def is_completed(self) -> bool:
        return self.old_snapshot is not None and self.new_snapshot is not None

    def __enter__(self) -> t.MutableMapping[t.Hashable, t.Any]:
        with (proc := psutil.Process()).oneshot():
            self.old_snapshot = snapshots.Snapshot.create(
                self.execution_id, proc
            )

        self.elapsed_ns_process = time.process_time_ns()
        self.elapsed_ns_perf = time.perf_counter_ns()

        return t.cast(
            t.MutableMapping[t.Hashable, t.Any], weakref.proxy(self.user)
        )

    def __exit__(
        self,
        exc_type: t.Optional[type[BaseException]],
        exc_value: t.Optional[BaseException],
        exc_tb: t.Optional[stdtypes.TracebackType],
    ) -> None:
        self.elapsed_ns_perf = time.perf_counter_ns() - self.elapsed_ns_perf
        self.elapsed_ns_process = (
            time.process_time_ns() - self.elapsed_ns_process
        )

        with (proc := psutil.Process()).oneshot():
            self.new_snapshot = snapshots.Snapshot.create(
                self.execution_id, proc
            )
