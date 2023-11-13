from __future__ import annotations

import datetime
import json
import pickle
import typing as t
import uuid
import zipfile

import pyzstd

from chemtrails import exceptions
from chemtrails import utils


if t.TYPE_CHECKING:
    from chemtrails import types as tt
    from chemtrails.trails import base

    BaseT = t.TypeVar("BaseT", bound=base.Base)


VERSION: int = 1

FILE_VERSION = "version.txt"
FILE_METADATA = "metadata.json"
FILE_CLASS_METADATA = "class_metadata.json"
FILE_DATA = "data.pickle"

ZSTD_PARAMS = {
    pyzstd.CParameter.compressionLevel: 3,
    pyzstd.CParameter.nbWorkers: 0,
}


def sniff(
    source: t.BinaryIO,
    *,
    validate: bool = False,
) -> t.Tuple[int, tt.ArchiveMetadata, tt.ClassMetadata]:
    with zipfile.ZipFile(file=source, mode="r") as zp:
        if validate and (badfile := zp.testzip()) is not None:
            raise exceptions.ArchiveBadFileError(badfile)

        with zp.open(FILE_METADATA, mode="r") as fp:
            data = json.load(fp)

        metadata: tt.ArchiveMetadata = {
            "hub_id": uuid.UUID(data["hub_id"]),
            "created_at": datetime.datetime.fromisoformat(data["created_at"]),
            "oid": data["oid"],
            "class_": data["class_"],
        }

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
            loaded: tt.ArchiveMetadata = json.load(fp)
            if utils.get_class_fqn(cls) != loaded["class_"]:
                raise exceptions.ArchiveClassMismatchError(loaded["class_"])

        with zp.open(FILE_DATA, mode="r") as fp:
            with pyzstd.ZstdFile(t.cast(t.BinaryIO, fp), mode="rb") as zfp:
                obj: BaseT = pickle.load(zfp)
                if not isinstance(obj, cls):
                    raise exceptions.ArchiveWrongObjectError(
                        obj.__class__, cls
                    )

                return obj


def save_object_to(target: t.BinaryIO, obj: base.Base) -> None:
    archive = zipfile.ZipFile(
        target,
        mode="w",
        compression=zipfile.ZIP_STORED,
    )

    with archive as zp:
        with zp.open(FILE_VERSION, mode="w") as fp:
            fp.write(f"{VERSION}\n".encode("latin1"))

        with zp.open(FILE_METADATA, mode="w") as fp:
            dumped = json.dumps(
                {
                    "hub_id": str(obj.hub_id),
                    "oid": obj.oid,
                    "created_at": obj.created_at.isoformat(),
                    "class_": utils.get_class_fqn(obj.__class__),
                }
            )
            fp.write(dumped.encode("utf-8"))

        with zp.open(FILE_CLASS_METADATA, mode="w") as fp:
            dumped = json.dumps(obj.class_metadata)
            fp.write(dumped.encode("utf-8"))

        with zp.open(FILE_DATA, mode="w") as fp:
            with pyzstd.ZstdFile(
                t.cast(t.BinaryIO, fp), mode="wb", level_or_option=ZSTD_PARAMS
            ) as zfp:
                pickle.dump(obj, file=zfp, protocol=pickle.HIGHEST_PROTOCOL)
