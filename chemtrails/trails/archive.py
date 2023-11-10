from __future__ import annotations

import json
import pickle
import typing as t
import zipfile

from chemtrails import exceptions
from chemtrails import types as tt


if t.TYPE_CHECKING:
    from chemtrails.trails import base

    BaseT = t.TypeVar("BaseT", bound=base.Base)


VERSION: int = 1

FILE_VERSION = "version.txt"
FILE_METADATA = "metadata.json"
FILE_CLASS_METADATA = "class_metadata.json"
FILE_DATA = "data.pickle"


def sniff(
    source: t.BinaryIO,
) -> t.Tuple[int, tt.ArchiveMetadata, tt.ClassMetadata]:
    with zipfile.ZipFile(file=source, mode="r") as zp:
        if (badfile := zp.testzip()) is not None:
            raise exceptions.ArchiveBadFileError(badfile)

        with zp.open(FILE_METADATA, mode="r") as fp:
            metadata = t.cast(tt.ArchiveMetadata, json.load(fp))

        with zp.open(FILE_CLASS_METADATA, mode="r") as fp:
            class_metadata = t.cast(tt.ClassMetadata, json.load(fp))

        version = int(zp.read(FILE_VERSION).rstrip().decode("latin1"))

        return version, metadata, class_metadata


def load_object_from(cls: type[BaseT], source: t.BinaryIO) -> BaseT:
    with zipfile.ZipFile(file=source, mode="r") as zp:
        if (badfile := zp.testzip()) is not None:
            raise exceptions.ArchiveBadFileError(badfile)

        read_version = int(zp.read(FILE_VERSION).rstrip().decode("latin1"))
        if read_version != VERSION:
            raise exceptions.ArchiveUnsupportedVersionError(read_version)

        with zp.open(FILE_METADATA, mode="r") as fp:
            loaded = t.cast(tt.ArchiveMetadata, json.load(fp))
            if _get_fqdn(cls) != loaded["class_"]:
                raise exceptions.ArchiveClassMismatchError(loaded["class_"])

        with zp.open(FILE_DATA, mode="r") as fp:
            return pickle.load(fp)  # type: ignore[no-any-return]


def save_object_to(target: t.BinaryIO, obj: base.Base) -> None:
    archive = zipfile.ZipFile(
        file=target,
        mode="w",
        compression=zipfile.ZIP_BZIP2,
        compresslevel=9,
    )

    with archive as zp:
        with zp.open(FILE_VERSION, mode="w") as fp:
            fp.write(f"{VERSION}\n".encode("latin1"))

        with zp.open(FILE_METADATA, mode="w") as fp:
            dumped = json.dumps(
                {
                    "execution_id": str(obj.execution_id),
                    "oid": obj.oid,
                    "created_at": obj.created_at.isoformat(),
                    "class_": _get_fqdn(obj.__class__),
                }
            )
            fp.write(dumped.encode("utf-8"))

        with zp.open(FILE_CLASS_METADATA, mode="w") as fp:
            dumped = json.dumps(obj.class_metadata)
            fp.write(dumped.encode("utf-8"))

        with zp.open(FILE_DATA, mode="w") as fp:
            pickle.dump(obj, file=fp, protocol=pickle.HIGHEST_PROTOCOL)


def _get_fqdn(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"
