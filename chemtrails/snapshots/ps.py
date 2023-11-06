from __future__ import annotations

import dataclasses
import pathlib


@dataclasses.dataclass(frozen=True, kw_only=True)
class Snapshot:
    # Amount of time that this process has been scheduled
    # in user mode, measured in clock ticks (divide by
    # sysconf(_SC_CLK_TCK)).  This includes guest time,
    # guest_time (time spent running a virtual CPU, see
    # below), so that applications that are not aware of
    # the guest time field do not lose that time from
    # their calculations.
    utime: int
    # Amount of time that this process has been scheduled
    # in kernel mode, measured in clock ticks (divide by
    # sysconf(_SC_CLK_TCK)).
    stime: int
    # Amount of time that this process's waited-for
    # children have been scheduled in user mode, measured
    # in clock ticks (divide by sysconf(_SC_CLK_TCK)).
    # (See also times(2).)  This includes guest time,
    # cguest_time (time spent running a virtual CPU, see
    # below).
    cutime: int
    # Amount of time that this process's waited-for
    # children have been scheduled in kernel mode,
    # measured in clock ticks (divide by
    # sysconf(_SC_CLK_TCK)).
    cstime: int
    # (Explanation for Linux 2.6) For processes running a
    # real-time scheduling policy (policy below; see
    # sched_setscheduler(2)), this is the negated
    # scheduling priority, minus one; that is, a number
    # in the range -2 to -100, corresponding to real-time
    # priorities 1 to 99.  For processes running under a
    # non-real-time scheduling policy, this is the raw
    # nice value (setpriority(2)) as represented in the
    # kernel.  The kernel stores nice values as numbers
    # in the range 0 (high) to 39 (low), corresponding to
    # the user-visible nice range of -20 to 19.
    #
    # Before Linux 2.6, this was a scaled value based on
    # the scheduler weighting given to this process.
    priority: int
    # Real-time scheduling priority, a number in the
    # range 1 to 99 for processes scheduled under a real-
    # time policy, or 0, for non-real-time processes (see
    # sched_setscheduler(2)).
    rt_priority: int
    # The nice value (see setpriority(2)), a value in the
    # range 19 (low priority) to -20 (high priority).
    nice: int
    # Number of threads in this process (since Linux
    # 2.6).  Before Linux 2.6, this field was hard coded
    # to 0 as a placeholder for an earlier removed field.
    num_threads: int
    # Current soft limit in bytes on the rss of the
    # process; see the description of RLIMIT_RSS in
    # getrlimit(2).
    rsslim: int
    # Aggregated block I/O delays, measured in clock
    # ticks (centiseconds).
    delayacct_blkio_ticks: int
    # Guest time of the process (time spent running a
    # virtual CPU for a guest operating system), measured
    # in clock ticks (divide by sysconf(_SC_CLK_TCK)).
    guest_time: int
    # Guest time of the process's children, measured in
    # clock ticks (divide by sysconf(_SC_CLK_TCK)).
    cguest_time: int

    @property
    def user_time(self) -> int:
        return self.utime - self.guest_time

    @property
    def children_time(self) -> int:
        return self.cstime - self.cguest_time

    @classmethod
    def create(cls) -> Snapshot:
        chunks = pathlib.Path("/proc/self/stat").read_text().split()
        return cls(
            utime=int(chunks[13]),
            stime=int(chunks[14]),
            cutime=int(chunks[15]),
            cstime=int(chunks[16]),
            priority=int(chunks[17]),
            rt_priority=int(chunks[39]),
            nice=int(chunks[18]),
            num_threads=int(chunks[19]),
            rsslim=int(chunks[24]),
            delayacct_blkio_ticks=int(chunks[41]),
            guest_time=int(chunks[42]),
            cguest_time=int(chunks[43]),
        )
