from __future__ import annotations

import binascii
import dataclasses
import datetime
import random
import struct
import time
import typing as t

from chemtrails import types as tt
from chemtrails import utils
from chemtrails.trails import archive


if t.TYPE_CHECKING:
    import typing_extensions as te


def _generate_id() -> tt.OID:
    tstamp_part = struct.pack(">Q", time.monotonic_ns())
    random_part = random.randbytes(8)

    return binascii.hexlify(tstamp_part + random_part).decode("latin1")


@dataclasses.dataclass()
class Base:
    hub_id: tt.HubID

    oid: tt.OID = dataclasses.field(init=False, default_factory=_generate_id)
    created_at: datetime.datetime = dataclasses.field(
        init=False,
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    @property
    def name(self) -> str:
        return f"{utils.get_class_fqn(self.__class__)}({self.oid})"

    @property
    def class_metadata(self) -> tt.ClassMetadata:
        return {}

    @classmethod
    def load_from(cls, source: t.BinaryIO) -> te.Self:
        return archive.load_object_from(cls, source)

    def save_to(self, destination: t.BinaryIO) -> None:
        archive.save_object_to(destination, self)
