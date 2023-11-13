from __future__ import annotations

import dataclasses
import ipaddress
import shlex
import typing as t

from chemtrails.cli.show import printlib


if t.TYPE_CHECKING:
    import pathlib

    from chemtrails import types as tt
    from chemtrails.trails import snapshots


def print_(snapshot: snapshots.Snapshot) -> None:
    printlib.header(snapshot)

    print()

    with printlib.section("Process information"):
        print_process(snapshot.process)

    print()

    with printlib.section("CPU"):
        print_cpu(snapshot.cpu)

    print()

    with printlib.section("Memory"):
        print_memory(snapshot.memory)

    print()

    with printlib.section("IO"):
        print_io(snapshot.io)

    print()

    with printlib.section("children"):
        print_children(snapshot.children)

    print()

    with printlib.section("threads"):
        print_threads(snapshot.threads)

    print()

    with printlib.section("files"):
        print_files(snapshot.files)

    print()

    with printlib.section("connections"):
        print_connections(snapshot.connections)


def print_process(proc: snapshots.Process) -> None:
    printlib.simple("Nice", proc.nice)

    with printlib.section("Limits"):
        printlib.table(
            {
                name: printlib.fmt_inline_table(dataclasses.asdict(value))
                for name, value in sorted(
                    proc.limits.items(), key=lambda el: el[0].name
                )
            },
        )


def print_cpu(cpu: snapshots.CPU) -> None:  # noqa: FNE008
    printlib.simple("count in use", cpu.num)
    printlib.simple(
        "affinity", ", ".join(str(el) for el in sorted(cpu.affinity or []))
    )

    with printlib.section("Execution times"):
        printlib.table(
            {
                "User": printlib.fmt_seconds(cpu.user),
                "System": printlib.fmt_seconds(cpu.kernel),
                "User of children": printlib.fmt_seconds(cpu.children_user),
                "System of children": printlib.fmt_seconds(
                    cpu.children_kernel
                ),
                "IO wait": printlib.fmt_seconds(cpu.iowait),
            },
        )


def print_memory(memory: snapshots.Memory) -> None:  # noqa: FNE008
    with printlib.section("Tracemalloc snapshot"):
        if snap := memory.snapshot:
            printlib.table(
                {
                    "Size": printlib.fmt_bytes(
                        sum(tr.size for tr in snap.traces)
                    ),
                    "Trace count": len(snap.traces),
                    "Traceback limit": snap.traceback_limit,
                },
            )
        else:
            print("tracemalloc was not active")

    with printlib.section("Sizes"):
        printlib.table(
            {
                "Resident set size (RSS)": printlib.fmt_bytes(memory.rss),
                "Virtual memory size (VMS)": printlib.fmt_bytes(memory.vms),
                "Unique set size (USS)": printlib.fmt_bytes(memory.uss),
                "Proportional set size (PSS)": printlib.fmt_bytes(memory.pss),
                "Swap size": printlib.fmt_bytes(memory.swap),
            },
        )


def print_io(io: snapshots.IO) -> None:  # noqa: FNE008
    if io.nice is None:
        print("-")
        return

    printlib.simple(
        "nice",
        printlib.fmt_inline_table(
            {"priority": io.nice.priority.name, "value": io.nice.value}
        ),
    )

    with printlib.section("counters"):
        printlib.table(
            {
                "read_count": io.read_count,
                "write_count": io.write_count,
                "other_count": (  # noqa: PAR001
                    io.other_count if io.other_count is not None else "-"
                ),
                "read_bytes": printlib.fmt_bytes(io.read_bytes),
                "write_bytes": printlib.fmt_bytes(io.write_bytes),
                "other_bytes": printlib.fmt_bytes(io.other_bytes),
                "read_chars": printlib.fmt_bytes(io.read_chars),
                "write_chars": printlib.fmt_bytes(io.write_chars),
            }
        )


def print_children(  # noqa: FNE008
    children: t.Mapping[tt.Pid, snapshots.Child]
) -> None:
    if not children:
        print("-")

    for pid, child in sorted(children.items()):
        with printlib.section(f"PID {pid}"):
            printlib.table(
                {
                    "name": child.name,
                    "executable": child.exe,
                    "cmdline": shlex.join(child.cmdline),
                }
            )


def print_threads(  # noqa: FNE008
    threads: t.Optional[dict[tt.Pid, snapshots.Thread]]
) -> None:
    if threads is None:
        print("-")
        return

    printlib.table(
        {
            thr_id: printlib.fmt_inline_table(
                {
                    "user": printlib.fmt_seconds(thread.user),
                    "system": printlib.fmt_seconds(thread.kernel),
                }
            )
            for thr_id, thread in sorted(threads.items())
        }
    )


def print_files(  # noqa: FNE008
    files: t.Mapping[pathlib.Path, snapshots.OpenFile]
) -> None:
    if not files:
        print("-")
        return

    printlib.table(
        {
            path: printlib.fmt_inline_table(
                {
                    "fd": printlib.fmt_value(data.fd),
                    "flag": printlib.fmt_value(
                        data.flag.name if data.flag else "-"
                    ),
                }
            )
            for path, data in sorted(files.items())
        }
    )


def print_connections(  # noqa: FNE008
    connections: snapshots.Connections,
) -> None:
    def fmt_address(addr: snapshots.NetworkAddress) -> str:
        if isinstance(addr.ip, ipaddress.IPv4Address):
            return f"{addr.ip}:{addr.port}"

        return f"[{addr.ip}]:{addr.port}"

    with printlib.section("TCP"):
        printlib.table(
            {
                f"{fmt_address(obj.local_address)} <-> "
                f"{fmt_address(obj.remote_address)}": printlib.fmt_inline_table(
                    {
                        "fd": printlib.fmt_value(obj.fd),
                        "status": printlib.fmt_value(obj.status),
                    }
                )
                for obj in sorted(
                    connections.tcp,
                    key=lambda obj: (obj.remote_address, obj.local_address),
                )
            }
        )

    with printlib.section("UDP"):
        printlib.table(
            {
                f"{fmt_address(obj.local_address)} <-> "
                f"{fmt_address(obj.remote_address)}": printlib.fmt_inline_table(
                    {
                        "fd": printlib.fmt_value(obj.fd),
                    }
                )
                for obj in sorted(
                    connections.udp,
                    key=lambda obj: (obj.remote_address, obj.local_address),
                )
            }
        )

    with printlib.section("UNIX"):
        printlib.table(
            {
                obj.path: printlib.fmt_inline_table(
                    {"fd": printlib.fmt_value(obj.fd), "type": obj.type_.name}
                )
                for obj in sorted(connections.unix, key=lambda obj: obj.path)
            }
        )
