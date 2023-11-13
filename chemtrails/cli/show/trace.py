from __future__ import annotations

import typing as t

from chemtrails.cli.show import printlib
from chemtrails.cli.show import snapshot


if t.TYPE_CHECKING:
    from chemtrails.trails import traces


def print_(trace: traces.Trace) -> None:
    printlib.header(trace)

    print()

    with printlib.section("user data"):
        printlib.table({k: repr(v) for k, v in trace.user.items()})

    print()

    with printlib.section("old snapshot"):
        if trace.old_snapshot is None:
            print("-")
        else:
            assert trace.old_snapshot is not None
            snapshot.print_(trace.old_snapshot)

    print()

    with printlib.section("spans"):
        print_span(trace.span)

    print()

    with printlib.section("new snapshot"):
        if trace.old_snapshot is None:
            print("-")
        else:
            assert trace.new_snapshot is not None
            snapshot.print_(trace.new_snapshot)


def print_span(span: traces.Span) -> None:  # noqa: FNE008
    span_str = (
        f"{span.trace_id}({span.oid}) "
        f"start={span.start}, finish={span.finish} "
        f"elapsed={span.elapsed}"
    )

    with printlib.section(span_str, with_formating=False):
        for child in span.children:
            print_span(child)
