from __future__ import annotations

import contextvars
import dataclasses
import threading
import time
import typing as t
import weakref

import psutil

from chemtrails.trails import base
from chemtrails.trails import snapshots


if t.TYPE_CHECKING:
    import types as stdtypes

    import typing_extensions as te

    from chemtrails import types as tt


class TraceDict(dict[t.Hashable, t.Any]):
    pass


@dataclasses.dataclass()
class Trace(base.Base):
    trace_id: str

    with_memory_snapshot: bool = dataclasses.field(default=False, kw_only=True)

    old_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    new_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    trace_map: TraceMap = dataclasses.field(
        init=False, default_factory=lambda: TraceMap()
    )
    user: TraceDict = dataclasses.field(init=False, default_factory=TraceDict)

    def __post_init__(self) -> None:
        self.trace_map.oid = self.oid

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
                self.execution_id,
                proc,
                with_memory_snapshot=self.with_memory_snapshot,
            )

        self.trace_map.push()

        return t.cast(
            t.MutableMapping[t.Hashable, t.Any], weakref.proxy(self.user)
        )

    def __exit__(
        self,
        exc_type: t.Optional[type[BaseException]],
        exc_value: t.Optional[BaseException],
        exc_tb: t.Optional[stdtypes.TracebackType],
    ) -> None:
        self.trace_map.pop()

        with (proc := psutil.Process()).oneshot():
            self.new_snapshot = snapshots.Snapshot.create(
                self.execution_id,
                proc,
                with_memory_snapshot=self.with_memory_snapshot,
            )


@dataclasses.dataclass(slots=True)
class TraceMap:
    oid: tt.OID = dataclasses.field(default="")
    children: list[TraceMap] = dataclasses.field(
        init=False, default_factory=list
    )
    start: tt.TimeNanoseconds = dataclasses.field(
        init=False, default_factory=time.perf_counter_ns
    )
    finish: tt.TimeNanoseconds = dataclasses.field(  # noqa: CCE001
        init=False, default=0
    )

    STACK: t.ClassVar[threading.local] = threading.local()

    @property
    def elapsed(self) -> tt.TimeNanoseconds:  # noqa: CCE001
        finish = time.perf_counter_ns() if not self.finish else self.finish
        return finish - self.start

    def is_in_progress(self) -> bool:
        return self.finish == 0

    def push(self) -> None:
        ctx_stack = self.get_stack()

        try:
            stack = ctx_stack.get()
        except LookupError:
            stack = []
            ctx_stack.set(stack)

        if stack:
            stack[-1].children.append(self)

        stack.append(self)

    def pop(self) -> None:  # noqa: CCE001
        stack = self.get_stack().get()
        if not stack:
            raise RuntimeError("Stack is unexpectecly empty")

        obj = stack.pop()
        if obj is not self:
            raise RuntimeError(
                f"Expect {self.oid} to be on a top of stack, got {obj.oid}"
            )

        self.finish = time.perf_counter_ns()

    @classmethod
    def get_stack(cls) -> contextvars.ContextVar[list[te.Self]]:
        if not hasattr(cls.STACK, "stack"):
            cls.STACK.stack = contextvars.ContextVar("trace_map_stack")

        return t.cast(
            contextvars.ContextVar[list],  # type: ignore[type-arg]
            cls.STACK.stack,
        )
