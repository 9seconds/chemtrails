from __future__ import annotations

import dataclasses
import gc
import pathlib
import re
import tracemalloc


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProcFS:
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
    locked: int

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
    def read(cls) -> ProcFS:
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
    generations: list[dict[str, int]] = dataclasses.field(
        init=False, default_factory=gc.get_stats
    )
    freeze_count: int = dataclasses.field(
        init=False, default_factory=gc.get_freeze_count
    )
    garbage: str = dataclasses.field(
        init=False, default_factory=lambda: repr(gc.garbage)
    )


@dataclasses.dataclass(frozen=True)
class Snapshot:
    snapshot: tracemalloc.Snapshot | None = dataclasses.field(
        init=False,
        default_factory=lambda: (
            tracemalloc.take_snapshot() if tracemalloc.is_tracing() else None
        ),
    )
    procfs: ProcFS = dataclasses.field(init=False, default_factory=ProcFS.read)
    gc_stats: GCStats = dataclasses.field(init=False, default_factory=GCStats)
