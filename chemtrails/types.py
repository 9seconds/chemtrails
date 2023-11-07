from __future__ import annotations

import typing as t


MetricNice: t.TypeAlias = int
MetricCPUID: t.TypeAlias = int
MetricBytes: t.TypeAlias = int
MetricCPUClocks: t.TypeAlias = int
MetricCPUTime: t.TypeAlias = float | int

FileDescriptor: t.TypeAlias = int
Pid: t.TypeAlias = int

JSON: t.TypeAlias = (
    dict[str, "JSON"] | list["JSON"] | None | int | float | str | bool
)
