from __future__ import annotations

import contextvars
import dataclasses
import traceback
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


def _get_source_line() -> tt.TraceID:
    frame = traceback.extract_stack(limit=3)[0]
    return f"{frame.filename}:{frame.lineno}"


@dataclasses.dataclass()
class Trace(base.Base):
    trace_id: tt.TraceID = dataclasses.field(default_factory=_get_source_line)

    with_memory_snapshot: bool = dataclasses.field(default=False, kw_only=True)

    old_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    new_snapshot: t.Optional[snapshots.Snapshot] = dataclasses.field(
        init=False,
        default=None,
    )
    span: Span = dataclasses.field(init=False, default_factory=lambda: Span())
    user: TraceDict = dataclasses.field(init=False, default_factory=TraceDict)

    def __post_init__(self) -> None:
        self.span.oid = self.oid
        self.span.trace_id = self.trace_id

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

        self.span.push()

        return t.cast(
            t.MutableMapping[t.Hashable, t.Any], weakref.proxy(self.user)
        )

    def __exit__(
        self,
        exc_type: t.Optional[type[BaseException]],
        exc_value: t.Optional[BaseException],
        exc_tb: t.Optional[stdtypes.TracebackType],
    ) -> None:
        self.span.pop()

        with (proc := psutil.Process()).oneshot():
            self.new_snapshot = snapshots.Snapshot.create(
                self.execution_id,
                proc,
                with_memory_snapshot=self.with_memory_snapshot,
            )


@dataclasses.dataclass(slots=True)
class Span:
    oid: tt.OID = dataclasses.field(default="")
    trace_id: tt.TraceID = dataclasses.field(default="")
    children: list[Span] = dataclasses.field(init=False, default_factory=list)
    start: tt.TimeNanoseconds = dataclasses.field(init=False, default=0)
    finish: tt.TimeNanoseconds = dataclasses.field(  # noqa: CCE001
        init=False, default=0
    )

    STACK: t.ClassVar[threading.local] = threading.local()

    @property
    def elapsed_ns(self) -> tt.TimeNanoseconds:
        if not self.start:
            return 0

        finish = self.finish or time.monotonic_ns()

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

        self.start = time.monotonic_ns()

    def pop(self) -> None:  # noqa: CCE001
        self.finish = time.monotonic_ns()

        stack = self.get_stack().get()
        if not stack:
            raise RuntimeError("Stack is unexpectecly empty")

        obj = stack.pop()
        if obj is not self:
            raise RuntimeError(
                f"Expect {self.oid} to be on a top of stack, got {obj.oid}"
            )

    @classmethod
    def get_stack(cls) -> contextvars.ContextVar[list[te.Self]]:
        if not hasattr(cls.STACK, "stack"):
            cls.STACK.stack = contextvars.ContextVar("trace_spans")

        return t.cast(
            contextvars.ContextVar[list],  # type: ignore[type-arg]
            cls.STACK.stack,
        )
