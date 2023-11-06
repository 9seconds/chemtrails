from __future__ import annotations

import dataclasses
import gc
import pathlib
import re
import tracemalloc


@dataclasses.dataclass(frozen=True, kw_only=True)
class Proc:
    rss: int
    pss: int
    pss_anon: int
    pss_file: int
    pss_shmem: int
    shared_clean: int
    shared_dirty: int
    private_clean: int
    private_dirty: int
    referenced: int
    anonymous: int
    lazyfree: int
    anonhugepages: int
    shmempmdmapped: int
    filepmdmapped: int
    shared_hugetlb: int
    private_hugetlb: int
    swap: int
    swappss: int
    locked: int  # noqa: CCE001

    RE = re.compile(
        r"""
        (?P<section>[a-zA-Z_]+):\s+  # section name
        (?P<counter>\d+)\s           # counter
        kB
    """,
        re.VERBOSE,
    )

    @property
    def uss(self) -> int:
        return self.private_clean + self.private_dirty

    @property
    def shared(self) -> int:
        return self.shared_clean + self.shared_dirty

    @classmethod
    def create(cls) -> Proc:
        data: dict[str, int] = {}

        with pathlib.Path("/proc/self/smaps_rollup").open() as fp:
            next(fp)  # skip 556715376000-7ffe255c6000 ---p 00000000 00:00 0

            for line in fp:
                matcher = cls.RE.match(line)
                if not matcher:
                    raise RuntimeError(f"Cannot correctly parse '{line}'")

                data[matcher.group(1).lower()] = int(matcher.group(2)) * 1024

        return cls(**data)


@dataclasses.dataclass(frozen=True)
class GCStats:
    generations: list[dict[str, int]]
    freeze_count: int
    garbage: str | None

    @classmethod
    def create(cls) -> GCStats:
        return cls(
            generations=gc.get_stats(),
            freeze_count=gc.get_freeze_count(),
            garbage=repr(gc.garbage) if gc.garbage else None,
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Snapshot:
    snapshot: tracemalloc.Snapshot | None
    proc: Proc
    gc_stats: GCStats

    @property
    def rss(self) -> int:
        return self.proc.rss

    @property
    def pss(self) -> int:
        return self.proc.pss

    @property
    def uss(self) -> int:
        return self.proc.uss

    @property
    def swap(self) -> int:  # noqa: FNE002
        return self.proc.swap

    @classmethod
    def create(cls) -> Snapshot:
        snapshot = None
        if tracemalloc.is_tracing():
            snapshot = tracemalloc.take_snapshot()

        return cls(
            snapshot=snapshot, proc=Proc.create(), gc_stats=GCStats.create()
        )
