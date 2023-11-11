from __future__ import annotations

import datetime
import ipaddress
import typing as t
import uuid


Nice: t.TypeAlias = int
CPUID: t.TypeAlias = int

SizeBytes: t.TypeAlias = int

TimeSeconds: t.TypeAlias = int | float
TimeNanoseconds: t.TypeAlias = TimeSeconds | int

FileDescriptor: t.TypeAlias = int
Pid: t.TypeAlias = int

NetworkIP: t.TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
NetworkPort: t.TypeAlias = int

OID: t.TypeAlias = str
HubID: t.TypeAlias = uuid.UUID
TraceID: t.TypeAlias = str

TraceDict: t.TypeAlias = t.MutableMapping[t.Hashable, t.Any]


class ArchiveMetadata(t.TypedDict):
    hub_id: uuid.UUID
    oid: str
    created_at: datetime.datetime
    class_: str


ClassMetadata: t.TypeAlias = dict[str, t.Any]
