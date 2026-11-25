"""What the application is doing to itself, kept so it can be looked at.

The point of this file is to make a future slowdown answerable rather than
arguable. When somebody says "it has got slower", the useful reply is a page
showing which screen, by how much, and since when -- not a conversation about
whether it feels slower than it used to.

Four decisions shape it:

**It is held in memory, not written to the database.** A row per request
would be tens of thousands of rows a month, in the same file as the invoices,
backed up every day, to answer a question nobody asks most weeks. The counts
here reset when the application restarts, which is a real limitation and is
said plainly on the page rather than hidden.

**It keeps summaries, not a log.** Every request updates a handful of numbers
per route -- count, total, maximum, and a small reservoir of recent timings
for the percentiles. That is a few hundred bytes per route, flat, however
long it runs. A ring buffer of individual requests would grow with traffic
and tell you less.

**Percentiles come from a sample, not from every request.** Keeping the
newest 200 timings per route gives a median and a 95th percentile that are
right to the nearest millisecond at this scale, which is far better than the
precision anybody needs to decide whether a page is slow.

**Measuring must cost less than it reveals.** One clock read, one lock, and
a handful of arithmetic per request -- measured at about 20 microseconds
against page times of 10 to 50 milliseconds, so under a tenth of one per
cent.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

#: How many recent timings to keep per route for the percentiles.
SAMPLE = 200

#: How many of the slowest individual requests to remember, across all
#: routes. Enough to recognise a pattern; few enough to read.
SLOWEST = 15

#: How often to note the memory figure. Every ten minutes for a day is 144
#: readings, which is a shape somebody can look at and say "that climbs".
MEMORY_EVERY = 600.0
MEMORY_POINTS = 144


# The name every unmatched request is filed under. A fixed string, because
# the alternative is a dictionary key per address somebody guessed at.
UNMATCHED = "(no such page)"

# How many timings a figure needs before it is worth printing. A median
# needs enough that it is a middle rather than an endpoint; a 95th
# percentile needs enough that the slowest one in twenty is an observation
# and not an extrapolation from a single visit.
MIN_FOR_MEDIAN = 3
MIN_FOR_P95 = 20


@dataclass
class Route:
    """What is known about one URL pattern."""

    name: str
    count: int = 0
    errors: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    queries: int = 0
    recent: deque[float] = field(default_factory=lambda: deque(maxlen=SAMPLE))
    last_seen: float = 0.0

    @property
    def mean_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    @property
    def queries_each(self) -> float:
        return self.queries / self.count if self.count else 0.0

    @property
    def median_ms(self) -> float | None:
        """The typical time, or None when too few visits to have one."""
        if len(self.recent) < MIN_FOR_MEDIAN:
            return None
        return self.percentile(0.5)

    @property
    def p95_ms(self) -> float | None:
        """The slow end, or None when too few visits to have one."""
        if len(self.recent) < MIN_FOR_P95:
            return None
        return self.percentile(0.95)

    def percentile(self, which: float) -> float:
        """A percentile of the recent sample. 0.5 is the median."""
        if not self.recent:
            return 0.0
        ordered = sorted(self.recent)
        index = min(len(ordered) - 1, int(round(which * (len(ordered) - 1))))
        return ordered[index]


class Telemetry:
    """Everything measured since the application started."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self.routes: dict[str, Route] = {}
        self.slowest: list[dict[str, Any]] = []
        self.memory: deque[tuple[float, float]] = deque(maxlen=MEMORY_POINTS)
        self._last_memory = 0.0
        self.note_memory()

    # -- recording ---------------------------------------------------------

    def record(self, name: str, ms: float, *, status: int, queries: int = 0,
               path: str = "") -> None:
        with self._lock:
            route = self.routes.get(name)
            if route is None:
                route = self.routes[name] = Route(name=name)

            route.count += 1
            route.total_ms += ms
            route.max_ms = max(route.max_ms, ms)
            route.queries += queries
            route.recent.append(ms)
            route.last_seen = time.time()
            if status >= 500:
                route.errors += 1

            # The slowest individual requests, with enough about each to go
            # and reproduce it. A median tells you a page is slow; one of
            # these tells you which page, with what on it.
            self.slowest.append({
                "name": name, "path": path, "ms": ms, "status": status,
                "queries": queries, # ISO ordering, like every other date in the application: an
                # English month name is the one piece of this page that
                # cannot be read on the Arabic side.
                "at": datetime.now().strftime("%m-%d %H:%M"),
            })
            self.slowest.sort(key=lambda r: r["ms"], reverse=True)
            del self.slowest[SLOWEST:]

        self.note_memory()

    def note_memory(self) -> None:
        """Record how much memory the process holds, occasionally.

        This is the one that answers "is it leaking". A single number says
        nothing -- an application that has loaded a big spreadsheet is
        *supposed* to be larger. A line that climbs all day and never comes
        back down is a leak.
        """
        now = time.time()
        if now - self._last_memory < MEMORY_EVERY and self.memory:
            return
        used = memory_mb()
        if used is None:
            return
        with self._lock:
            self._last_memory = now
            self.memory.append((now, used))

    # -- reading -----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            routes = sorted(
                self.routes.values(),
                key=lambda r: r.total_ms,
                reverse=True,
            )
            total_requests = sum(r.count for r in routes)
            total_errors = sum(r.errors for r in routes)
            busiest = max(routes, key=lambda r: r.count, default=None)
            slowest_route = max(
                (r for r in routes if r.count >= 3),
                key=lambda r: r.percentile(0.5),
                default=None,
            )
            memory = list(self.memory)
            slowest = list(self.slowest)

        return {
            "uptime_s": time.time() - self.started,
            "started": datetime.fromtimestamp(self.started),
            "routes": routes,
            "requests": total_requests,
            "errors": total_errors,
            "busiest": busiest,
            "slowest_route": slowest_route,
            "slowest": slowest,
            "memory": memory,
            "memory_now": memory[-1][1] if memory else None,
            "memory_first": memory[0][1] if memory else None,
        }

    def reset(self) -> None:
        """Start counting again -- after a change, to see whether it helped."""
        with self._lock:
            self.routes.clear()
            self.slowest.clear()
            self.started = time.time()


def memory_mb() -> float | None:
    """How much memory this process is holding, in megabytes.

    Read from the operating system without a library: `psutil` would do this
    in one line and wants a compiler on Windows, which this project does not
    ask anybody to have. Linux keeps it in /proc; Windows answers through a
    call into its own kernel32. Where neither works the page says the figure
    is unavailable rather than inventing one.
    """
    try:
        with open("/proc/self/statm") as handle:                # Linux
            pages = int(handle.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1_048_576
    except (OSError, ValueError, IndexError, AttributeError):
        pass

    try:                                                        # Windows
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        ):
            return counters.WorkingSetSize / 1_048_576
    except Exception:
        pass

    return None


#: The one instance. A module-level value rather than something passed
#: around: every request writes to it, and threading it through forty route
#: signatures would be forty chances to forget.
stats = Telemetry()
