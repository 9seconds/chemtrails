from __future__ import annotations

import dataclasses
import enum
import ipaddress
import os
import pathlib
import socket
import tracemalloc
import typing as t

import psutil

from chemtrails.trails import base


if t.TYPE_CHECKING:
    import uuid

    import typing_extensions as te

    from chemtrails import types as tt


LimitName = enum.Enum(  # type: ignore[misc]
    "LimitName",
    {
        name: getattr(psutil, name)
        for name in dir(psutil)
        if name.startswith("RLIMIT_")
    },
)

IOPriority = enum.Enum(  # type: ignore[misc]
    "IOPriority",
    {
        name: getattr(psutil, name)
        for name in dir(psutil)
        if name.startswith("IOPRIO_")
    },
)

OpenFlag = enum.IntFlag(  # type: ignore[misc]
    "OpenFlag",
    {
        # for some reason, O_LARGEFILE == 0 and that makes an incorrect flag
        name.replace("O_", ""): getattr(os, name)
        if name != "O_LARGEFILE"
        else 32768
        for name in dir(os)
        if name.startswith("O_")
    },
)

SocketStatus = enum.Enum(  # type: ignore[misc]
    "SocketStatus",
    {
        name.replace("CONN_", ""): getattr(psutil, name)
        for name in dir(psutil)
        if name.startswith("CONN_")
    },
)


@dataclasses.dataclass(kw_only=True)
class Snapshot(base.Base):
    memory: Memory
    process: Process
    cpu: CPU
    io: IO
    connections: Connections
    children: dict[tt.Pid, Child]
    threads: t.Optional[dict[tt.Pid, Thread]]
    files: dict[pathlib.Path, OpenFile]

    @classmethod
    def create(
        cls,
        execution_id: uuid.UUID,
        proc: psutil.Process,
        *,
        with_memory_snapshot: bool = True,
    ) -> te.Self:
        try:
            threads = {
                thr.id: Thread(user=thr.user_time, kernel=thr.system_time)
                for thr in proc.threads()
            }
        except psutil.AccessDenied:
            threads = None

        return cls(
            execution_id=execution_id,
            children={
                cproc.pid: Child(
                    name=cproc.name(),
                    cmdline=cproc.cmdline(),
                    exe=cproc.exe(),
                )
                for cproc in proc.children()
            },
            threads=threads,
            files={
                pathlib.Path(f_.path): OpenFile(
                    fd=f_.fd if f_.fd != -1 else None,
                    flag=OpenFlag(f_.flags)  # type: ignore[attr-defined]
                    if hasattr(f_, "flags")
                    else None,
                )
                for f_ in proc.open_files()
            },
            cpu=CPU.create(proc),
            io=IO.create(proc),
            memory=Memory.create(proc, with_snapshot=with_memory_snapshot),
            process=Process.create(proc),
            connections=Connections.create(proc),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Memory:
    snapshot: t.Optional[tracemalloc.Snapshot]
    rss: tt.SizeBytes
    vms: tt.SizeBytes
    uss: t.Optional[tt.SizeBytes]
    pss: t.Optional[tt.SizeBytes]
    swap: t.Optional[tt.SizeBytes]

    @classmethod
    def create(
        cls, proc: psutil.Process, *, with_snapshot: bool = True
    ) -> Memory:
        mem_info = proc.memory_full_info()

        snapshot = None
        if with_snapshot and tracemalloc.is_tracing():
            snapshot = tracemalloc.take_snapshot()

        return cls(
            snapshot=snapshot,
            rss=mem_info.rss,
            vms=mem_info.vms,
            uss=getattr(mem_info, "uss", None),
            pss=getattr(mem_info, "pss", None),
            swap=getattr(mem_info, "swap", None),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Process:
    nice: tt.Nice
    limits: dict[LimitName, LimitValue]

    @classmethod
    def create(cls, proc: psutil.Process) -> Process:
        limits = {}

        if hasattr(proc, "rlimit"):
            for limit in LimitName:
                try:
                    soft, hard = proc.rlimit(limit.value)
                except psutil.AccessDenied:
                    pass
                else:
                    limits[limit] = LimitValue(soft=soft, hard=hard)

        return cls(
            nice=proc.nice(),
            limits=limits,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class CPU:
    user: tt.TimeSeconds
    kernel: tt.TimeSeconds
    children_user: tt.TimeSeconds
    children_kernel: tt.TimeSeconds
    iowait: t.Optional[tt.TimeSeconds]
    affinity: t.Optional[list[tt.CPUID]]
    num: t.Optional[int]

    @classmethod
    def create(cls, proc: psutil.Process) -> CPU:
        times = proc.cpu_times()

        return cls(
            user=times.user,
            kernel=times.system,
            children_user=times.children_user,
            children_kernel=times.children_system,
            iowait=getattr(times, "iowait", None),
            affinity=(
                proc.cpu_affinity() if hasattr(proc, "cpu_affinity") else None
            ),
            num=proc.cpu_num() if hasattr(proc, "cpu_num") else None,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class IO:
    nice: t.Optional[IONice]
    read_count: int
    write_count: int
    other_count: t.Optional[int]
    read_bytes: t.Optional[tt.SizeBytes]
    write_bytes: t.Optional[tt.SizeBytes]
    other_bytes: t.Optional[tt.SizeBytes]
    read_chars: t.Optional[tt.SizeBytes]
    write_chars: t.Optional[tt.SizeBytes]

    @classmethod
    def create(cls, proc: psutil.Process) -> IO:
        nice = None
        if hasattr(proc, "ionice"):
            value = proc.ionice()
            nice = IONice(
                priority=IOPriority[value.ioclass.name],  # type: ignore
                value=value.value,
            )

        cnt = proc.io_counters()

        return cls(
            nice=nice,
            read_count=cnt.read_count,
            write_count=cnt.write_count,
            other_count=getattr(cnt, "other_count", None),
            read_bytes=getattr(cnt, "read_bytes", None),
            write_bytes=getattr(cnt, "write_bytes", None),
            other_bytes=getattr(cnt, "other_bytes", None),
            read_chars=getattr(cnt, "read_chars", None),
            write_chars=getattr(cnt, "write_chars", None),
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Connections:
    unix: list[UnixSocket]
    tcp: list[TCPSocket]
    udp: list[UDPSocket]

    @classmethod
    def create(cls, proc: psutil.Process) -> Connections:
        unix = []
        tcp = []
        udp = []

        for conn in proc.connections("all"):
            if not conn.laddr:
                continue

            match (conn.type, conn.family):
                case [_, socket.AF_UNIX]:
                    unix.append(
                        UnixSocket(
                            fd=conn.fd,
                            type_=socket.SocketKind(conn.type),
                            path=pathlib.Path(
                                t.cast(str, conn.laddr)
                            ).absolute(),
                        )
                    )
                case [socket.SOCK_STREAM, _]:
                    tcp.append(
                        TCPSocket(
                            fd=conn.fd,
                            local_address=NetworkAddress.create(conn.laddr),
                            remote_address=NetworkAddress.create(conn.raddr),
                            status=SocketStatus[conn.status],
                        )
                    )
                case [socket.SOCK_DGRAM, _]:
                    udp.append(
                        UDPSocket(
                            fd=conn.fd,
                            local_address=NetworkAddress.create(conn.laddr),
                            remote_address=NetworkAddress.create(conn.raddr),
                        )
                    )

        return cls(
            unix=unix,
            tcp=tcp,
            udp=udp,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class IONice:
    priority: IOPriority
    value: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class LimitValue:
    soft: int
    hard: int


@dataclasses.dataclass(frozen=True, kw_only=True)
class Child:
    name: str
    cmdline: list[str]
    exe: str


@dataclasses.dataclass(frozen=True, kw_only=True)
class Thread:
    user: tt.TimeSeconds
    kernel: tt.TimeSeconds


@dataclasses.dataclass(frozen=True, kw_only=True)
class OpenFile:
    fd: t.Optional[tt.FileDescriptor]
    flag: t.Optional[OpenFlag]


@dataclasses.dataclass(frozen=True, kw_only=True)
class NetworkAddress:
    ip: tt.NetworkIP
    port: tt.NetworkPort

    @classmethod
    def create(cls, pair: t.Tuple[str, int]) -> NetworkAddress:
        return cls(ip=ipaddress.ip_address(pair[0]), port=pair[1])


@dataclasses.dataclass(frozen=True, kw_only=True)
class Socket:
    fd: tt.FileDescriptor


@dataclasses.dataclass(frozen=True, kw_only=True)
class IPSocket(Socket):
    local_address: NetworkAddress
    remote_address: NetworkAddress


@dataclasses.dataclass(frozen=True, kw_only=True)
class UDPSocket(IPSocket):
    pass


@dataclasses.dataclass(frozen=True, kw_only=True)
class TCPSocket(IPSocket):
    status: SocketStatus


@dataclasses.dataclass(frozen=True, kw_only=True)
class UnixSocket(Socket):
    type_: socket.SocketKind
    path: pathlib.Path
