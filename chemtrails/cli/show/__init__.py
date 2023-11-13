from __future__ import annotations

import argparse
import contextlib
import sys
import typing as t

from chemtrails import exceptions
from chemtrails import trails
from chemtrails.cli.show import snapshot
from chemtrails.cli.show import trace
from chemtrails.trails import archive


if t.TYPE_CHECKING:
    from chemtrails.trails import base


def register(parser: argparse._SubParsersAction[t.Any]) -> None:
    subparser = parser.add_parser(
        "show", description="Show information about snapshots and traces"
    )

    subparser.add_argument(
        "file", type=argparse.FileType(mode="rb"), help="File to show"
    )
    subparser.set_defaults(func=main)


def main(options: argparse.Namespace) -> None:
    with contextlib.closing(options.file):
        loaded = load_object_from_file(options.file)

    match loaded:
        case trails.Snapshot():
            snapshot.print_(loaded)

        case trails.Trace():
            trace.print_(loaded)

        case _:
            sys.exit(f"Unknown object in {options.file.name}")


def load_object_from_file(source: t.BinaryIO) -> base.Base | None:
    for cls in trails.Snapshot, trails.Trace:
        try:
            return archive.load_object_from(cls, source)
        except exceptions.ArchiveClassMismatchError:
            source.seek(0, 0)

    return None
