from __future__ import annotations

import binascii
import dataclasses
import enum
import ipaddress
import os
import pathlib
import re
import typing as t


OpenFlags = enum.IntFlag(  # type: ignore[misc]
    "OpenFlags",
    {
        name.replace("O_", ""):
        # for some really bizzare reason, O_LARGEFILE is 0 here
        getattr(os, name) if name != "O_LARGEFILE" else 32768
        for name in dir(os)
        if name.startswith("O_")
    },
)

_tcp_states = {
    name: val
    for val, name in enumerate(
        (
            "TCP_ESTABLISHED",
            "TCP_SYN_SENT",
            "TCP_SYN_RECV",
            "TCP_FIN_WAIT1",
            "TCP_FIN_WAIT2",
            "TCP_TIME_WAIT",
            "TCP_CLOSE",
            "TCP_CLOSE_WAIT",
            "TCP_LAST_ACK",
            "TCP_LISTEN",
            "TCP_CLOSING",
            "TCP_NEW_SYN_RECV",
            "TCP_MAX_STATES",
        ),
        start=1,
    )
}
_tcp_states.update(
    {
        name.replace("TCP", "TCPF"): 1 << val
        for name, val in list(_tcp_states.items())
    }
)
TCPState = enum.IntEnum("TCPStates", _tcp_states)  # type: ignore[misc]
del _tcp_states


@dataclasses.dataclass(frozen=True)
class Address:
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    port: int

    @classmethod
    def parse_procfs(cls, addr: str, port: str) -> Address:
        return cls(
            ip=ipaddress.ip_address(binascii.unhexlify(addr)[::-1]),
            port=int(port, 16),
        )


@dataclasses.dataclass(frozen=True)
class Socket:
    local_address: Address
    remote_address: Address


@dataclasses.dataclass(frozen=True)
class TCPSocket(Socket):
    state: TCPState


@dataclasses.dataclass(frozen=True)
class UDPSocket(Socket):
    pass


@dataclasses.dataclass(frozen=True, kw_only=True)
class Proc:
    # I/O counter: chars read
    # The number of bytes which this task has caused to be read from storage.
    # This is simply the sum of bytes which this process passed to read()
    # and pread(). It includes things like tty IO and it is unaffected by
    # whether or not actual physical disk IO was required (the read might
    # have been satisfied from pagecache).
    rchar: int
    # I/O counter: chars written
    # The number of bytes which this task has caused, or shall cause to be
    # written to disk. Similar caveats apply here as with rchar.
    wchar: int
    # I/O counter: read syscalls
    # Attempt to count the number of read I/O operations, i.e. syscalls like
    # read() and pread().
    syscr: int
    # I/O counter: write syscalls
    # Attempt to count the number of write I/O operations, i.e. syscalls like
    # write() and pwrite().
    syscw: int
    # I/O counter: bytes read
    # Attempt to count the number of bytes which this process really did
    # cause to be fetched from the storage layer. Done at the submit_bio()
    # level, so it is accurate for block-backed filesystems. <please add
    # status regarding NFS and CIFS at a later time>
    read_bytes: int
    # I/O counter: bytes written
    # Attempt to count the number of bytes which this process caused to be
    # sent to the storage layer. This is done at page-dirtying time.
    write_bytes: int
    # The big inaccuracy here is truncate. If a process writes 1MB to a file
    # and then deletes the file, it will in fact perform no writeout. But it
    # will have been accounted as having caused 1MB of write.
    #
    # In other words: The number of bytes which this process caused to not
    # happen, by truncating pagecache. A task can cause "negative" IO too.
    # If this task truncates some dirty pagecache, some IO which another
    # task has been accounted for (in its write_bytes) will not be happening.
    # We _could_ just subtract that from the truncating task's write_bytes,
    # but there is information loss in doing that.
    cancelled_write_bytes: int

    @property
    def io_operations(self) -> int:
        return self.syscr + self.syscw

    @property
    def real_write_bytes(self) -> int:  # noqa: FNE002
        return self.write_bytes - self.cancelled_write_bytes

    @classmethod
    def create(cls) -> Proc:
        data: dict[str, int] = {}

        with pathlib.Path("/proc/self/io").open() as fp:
            for line in fp:
                matcher = re.match(r"(\w+):\s+(\d+)", line)
                if not matcher:
                    raise RuntimeError(f"Cannot correctly parse {line}")

                data[matcher.group(1)] = int(matcher.group(2))

        return cls(**data)


@dataclasses.dataclass(frozen=True)
class Snapshot:
    fd_count: int
    files: dict[pathlib.Path, OpenFlags]
    tcp_sockets: list[TCPSocket]
    udp_sockets: list[UDPSocket]
    proc: Proc  # noqa: CCE001

    NET_RE = re.compile(
        r"""
        \s*
        \d+:\s+  # seq number
        (?P<local_ip>[A-F0-9]+):(?P<local_port>[A-F0-9]+)\s+
        (?P<remote_ip>[A-F0-9]+):(?P<remote_port>[A-F0-9]+)\s+
        (?P<state>[A-F0-9]{2})\s+
        \S+\s+  # tx_queue:rx_queue
        \S+\s+  # tr, tm->when
        \S+\s+  # retrnsmt
        \S+\s+  # uid
        \S+\s+  # timeout
        (?P<inode>\d+)
        .*$    # do not care after
    """,
        re.VERBOSE,
    )

    @classmethod
    def _scan_net_files(
        cls, inodes: set[str], *net_files: str
    ) -> t.Iterator[re.Match[str]]:
        for path in net_files:
            with pathlib.Path(path).open() as fp:
                next(fp)  # skip header

                for line in fp:
                    matcher = cls.NET_RE.match(line)
                    if not matcher:
                        raise RuntimeError(f"Cannot parse {line} from {path}")

                    if matcher.group("inode") in inodes:
                        yield matcher

    @classmethod
    def read(cls) -> Snapshot:
        fd_count = 0
        socket_inodes = set()
        files = {}

        for descr in pathlib.Path("/proc/self/fd").iterdir():
            fd_count += 1
            linkto = descr.resolve()

            if os.fspath(linkto).startswith("/dev/pts"):
                continue

            if inode := re.match(r"socket:\[(\d+)\]", linkto.name):
                socket_inodes.add(inode.group(1))
                continue

            fdinfo = pathlib.Path("/proc/self/fdinfo").joinpath(descr.name)

            try:
                text = fdinfo.read_text()
            except FileNotFoundError:
                continue

            if flags := re.search(r"^flags:\s+([0-7]+)", text, re.MULTILINE):
                files[linkto] = OpenFlags(int(flags.group(1), 8))

        return Snapshot(
            fd_count=fd_count,
            files=files,
            proc=Proc.create(),
            tcp_sockets=[
                TCPSocket(
                    local_address=Address.parse_procfs(
                        m.group("local_ip"), m.group("local_port")
                    ),
                    remote_address=Address.parse_procfs(
                        m.group("remote_ip"), m.group("remote_port")
                    ),
                    state=TCPState(int(m.group("state"), 16)),
                )
                for m in cls._scan_net_files(
                    socket_inodes, "/proc/self/net/tcp", "/proc/self/net/tcp6"
                )
            ],
            udp_sockets=[
                UDPSocket(
                    local_address=Address.parse_procfs(
                        m.group("local_ip"), m.group("local_port")
                    ),
                    remote_address=Address.parse_procfs(
                        m.group("remote_ip"), m.group("remote_port")
                    ),
                )
                for m in cls._scan_net_files(
                    socket_inodes, "/proc/self/net/udp", "/proc/self/net/udp"
                )
            ],
        )
