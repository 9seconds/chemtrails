from __future__ import annotations

import contextlib
import enum
import functools
import io
import textwrap
import typing as t


if t.TYPE_CHECKING:
    from chemtrails import types as tt
    from chemtrails.trails import base


T = t.TypeVar("T")


@contextlib.contextmanager
def section(
    title: str, *, with_formating: bool = True
) -> t.Iterator[t.TextIO]:
    out = io.StringIO()

    if with_formating:
        title = f"{title.title()}:"

    with contextlib.redirect_stdout(out):
        yield out

    value = textwrap.indent(out.getvalue().rstrip(), "  ")

    print(title)

    if value.lstrip():
        print(value)


def header(obj: base.Base) -> None:
    print(f"# {obj.__class__.__name__}({obj.oid})")

    simple("Hub", obj.hub_id)
    simple("Created at", obj.created_at.isoformat())


def simple(key: t.Any, value: t.Any) -> None:
    print(f"{fmt_key(key).title()}: {fmt_value(value)}")


def table(table: t.Mapping[t.Hashable, t.Any]) -> None:
    if not table:
        print("-")
        return

    str_table = {f"{fmt_key(k)}:  ": fmt_value(v) for k, v in table.items()}
    max_key_len = max(len(key) for key in str_table)
    max_value_len = max(len(value) for value in str_table.values())

    for key, value in str_table.items():
        print(f"{key.ljust(max_key_len)}{value.rjust(max_value_len)}")


def _fmt_optional(
    optional_value: str = "-",
) -> t.Callable[[t.Callable[[T], str]], t.Callable[[t.Optional[T]], str]]:
    def outer_decorator(
        func: t.Callable[[T], str]
    ) -> t.Callable[[t.Optional[T]], str]:
        @functools.wraps(func)
        def inner_decorator(value: t.Optional[T]) -> str:
            if value is None:
                return optional_value

            return func(value)

        return inner_decorator

    return outer_decorator


def fmt_key(key: t.Any) -> str:  # noqa: FNE008
    if isinstance(key, enum.Enum):
        key = key.name

    return str(key).strip().removesuffix(":")


@_fmt_optional()
def fmt_value(value: t.Any) -> str:  # noqa: FNE008
    if isinstance(value, enum.Enum):
        value = value.value

    return str(value).strip()


def fmt_inline_table(table: t.Mapping[t.Any, t.Any]) -> str:  # noqa: FNE008
    return ", ".join(
        f"{fmt_key(k)}={fmt_value(v)}" for k, v in sorted(table.items())
    )


@_fmt_optional()
def fmt_bytes(value: tt.SizeBytes) -> str:
    return f"{value} bytes"


@_fmt_optional()
def fmt_seconds(value: tt.TimeSeconds) -> str:
    return f"{value:0.4f} seconds"
