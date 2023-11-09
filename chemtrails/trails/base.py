from __future__ import annotations

import binascii
import dataclasses
import datetime
import json
import pickle
import random
import struct
import time
import typing as t
import zipfile

from chemtrails import exceptions
from chemtrails import trails
from chemtrails import types as tt


if t.TYPE_CHECKING:
    import uuid

    import typing_extensions as te


def _generate_id() -> str:
    tstamp_part = struct.pack(">Q", time.monotonic_ns())
    random_part = random.randbytes(8)

    return binascii.hexlify(tstamp_part + random_part).decode("latin1")


@dataclasses.dataclass()
class Base:
    execution_id: uuid.UUID

    oid: str = dataclasses.field(init=False, default_factory=_generate_id)
    created_at: datetime.datetime = dataclasses.field(
        init=False,
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    @property
    def class_metadata(self) -> tt.ClassMetadata:
        return {}

    @classmethod
    def load_from(cls, source: t.BinaryIO) -> te.Self:
        with zipfile.ZipFile(file=source, mode="r") as zp:
            read_version = int(
                zp.read("version.txt").rstrip().decode("latin1")
            )
            if read_version != trails.VERSION:
                raise exceptions.UnsupportedVersionError(read_version)

            with zp.open("metadata.json", mode="r") as fp:
                loaded = t.cast(tt.ArchiveMetadata, json.load(fp))
                if cls.__name__ != loaded["class_"]:
                    raise exceptions.ClassMismatchError(loaded["class_"])

            with zp.open("data.pickle", mode="r") as fp:
                return pickle.load(fp)  # type: ignore[no-any-return]

    def save_to(self, destination: t.BinaryIO) -> None:
        archive = zipfile.ZipFile(
            file=destination,
            mode="w",
            compression=zipfile.ZIP_BZIP2,
            compresslevel=9,
        )

        with archive as zp:
            with zp.open("version.txt", mode="w") as fp:
                fp.write(f"{trails.VERSION}\n".encode("latin1"))

            with zp.open("metadata.json", mode="w") as fp:
                dumped = json.dumps({
                    "execution_id": str(self.execution_id),
                    "oid": self.oid,
                    "created_at": self.created_at.isoformat(),
                    "class_": self.__class__.__name__,
                })
                fp.write(dumped.encode("utf-8"))

            with zp.open("class_metadata.json", mode="w") as fp:
                dumped = json.dumps(self.class_metadata)
                fp.write(dumped.encode("utf-8"))

            with zp.open("data.pickle", mode="w") as fp:
                pickle.dump(self, file=fp, protocol=pickle.HIGHEST_PROTOCOL)
