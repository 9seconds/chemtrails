from __future__ import annotations

import contextlib
import typing as t
import zipfile


ZIP_COMPRESSION_PRIORITY = (
    zipfile.ZIP_LZMA,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_STORED,
)


@contextlib.contextmanager
def write_zip(
    fileobj: t.BinaryIO, version: int
) -> t.Iterator[zipfile.ZipFile]:
    for compression in ZIP_COMPRESSION_PRIORITY:
        try:
            archive = zipfile.ZipFile(
                fileobj,
                mode="w",
                compression=compression,
                compresslevel=9,
            )
        except RuntimeError:
            continue
        else:
            break

    with archive as myzip:
        with myzip.open("version.txt", mode="w") as fp:
            fp.write(f"{version}\n".encode("latin1"))

        yield myzip


@contextlib.contextmanager
def read_zip(fileobj: t.BinaryIO, version: int) -> t.Iterator[zipfile.ZipFile]:
    with zipfile.ZipFile(fileobj, mode="r") as archive:  # noqa: SIM117
        with archive.open("version.txt", mode="r") as fp:
            if version != (rv := int(fp.read().strip().decode("latin1"))):
                raise ValueError(f"Unsupported version {rv}")

            yield archive
