"""RSS sampler: a spawned process that streams /proc/<pid>/status samples to a CSV file.

Sample times come from time.perf_counter_ns() (CLOCK_MONOTONIC), the same clock as the plan
times of the runner and the event log of the CU memtracker.
"""
from __future__ import annotations

import csv
from pathlib import Path
import time


def process_identity(pid: int, proc_root: Path = Path('/proc')) -> str:
    """Return the process start time (clock ticks since boot); it changes when the PID is reused."""
    stat = (proc_root / str(pid) / 'stat').read_text()

    # comm (field 2) may contain spaces and parentheses, so split after the last ')'
    fields = stat[stat.rindex(')') + 2:].split()

    return fields[19]  # field 22 is starttime; this slice begins at field 3


def read_rss(pid: int, proc_root: Path = Path('/proc')) -> int:
    """Return VmRSS in bytes, parsed from /proc/<pid>/status."""
    for line in (proc_root / str(pid) / 'status').read_text().splitlines():
        fields = line.split()

        if fields and fields[0] == 'VmRSS:':
            return int(fields[1]) * 1024  # the kernel labels the unit kB but means KiB

    raise ValueError(f'VmRSS missing in /proc/{pid}/status')


def collect_samples(pid, interval, path, stop, pipe):
    """Spawned process: append one RSS sample every `interval` seconds to `path` until `stop` is set."""
    try:
        identity = process_identity(pid)  # start time pins the sampled process
        read_rss(pid)  # fail before announcing readiness if the file cannot be read

        cpu_start, wall_start = time.process_time(), time.perf_counter()
        count, read_total_ns, read_max_ns = 0, 0, 0

        # line buffering flushes every complete row, so a crash keeps the partial trace
        with Path(path).open('w', newline='', buffering=1) as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp_ns', 'rss_bytes'])
            deadline = time.perf_counter()

            while True:
                start = time.perf_counter_ns()
                rss = read_rss(pid)
                end = time.perf_counter_ns()

                # a changed start time means the PID now belongs to another process
                if process_identity(pid) != identity:
                    raise ProcessLookupError(f'CU PID {pid} was reused')

                # the read takes time; its midpoint approximates the instant of the snapshot
                writer.writerow([(start + end) // 2, rss])
                count += 1
                read_total_ns += end - start
                read_max_ns = max(read_max_ns, end - start)

                if count == 1:
                    pipe.send({'type': 'ready', 'pid_start_ticks': identity})  # unblocks MemorySession.start()

                if stop.is_set():
                    break  # the final sample brackets the last interval

                deadline += interval
                now = time.perf_counter()

                if deadline < now:
                    deadline = now + interval  # overrun: skip the missed ticks instead of catching up

                stop.wait(max(0, deadline - now))  # an Event wait allows a prompt shutdown

        pipe.send({'type': 'stopped', 'sample_count': count,
                   'mean_read_ms': read_total_ns / count / 1e6, 'max_read_ms': read_max_ns / 1e6,
                   'collector_cpu_seconds': time.process_time() - cpu_start,
                   'collector_wall_seconds': time.perf_counter() - wall_start})

    except Exception as error:
        # report to the parent instead of leaving a silently truncated trace
        pipe.send({'type': 'error', 'error': f'{type(error).__name__}: {error}'})

    finally:
        pipe.close()


def load_samples(path: Path) -> list[dict]:
    """Load the sample CSV as int dicts, skipping a final row that is still being written."""
    result = []

    with path.open(newline='') as stream:
        for row in csv.DictReader(stream):
            try:
                result.append({key: int(value) for key, value in row.items()})
            except (TypeError, ValueError):
                continue  # a read can race the unfinished last row

    return result
