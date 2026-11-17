"""Read the CU's per-operator memory log and derive occupancy numbers from it.

The log is written by computeUnit/src/infrastructure/MemTracker.cpp (RAM_TRACKING build):
a 32-byte header followed by raw 32-byte events. Values are requested capacity (virtual
memory attributed to the producing operator), not RSS.
"""
from __future__ import annotations

import csv
import struct
from collections import defaultdict
from pathlib import Path

# Must match MemTracker.hpp: Event and FileHeader.
EVENT = struct.Struct('<QIIqB7x')   # t_ns, plan, item, value, kind
HEADER = struct.Struct('<8sIIQQ')   # magic, version, event_size, capacity, start_ns
MAGIC, VERSION = b'RUBIMEM1', 1
DELTA, TEMP, DROPPED = 0, 1, 2      # value = +/- output bytes / absolute temp level / events lost
MIB = 1024 ** 2


def load_events(path: Path, since_ns: int = 0) -> list[tuple]:
    """Return (t_ns, plan, item, value, kind) tuples that are not older than since_ns."""
    data = Path(path).read_bytes()
    magic, version, event_size, _capacity, _start = HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION or event_size != EVENT.size:
        raise ValueError(f'{path}: not a memtrack log of the expected layout')
    body = data[HEADER.size:]
    body = body[:len(body) - len(body) % EVENT.size]  # ignore a torn last record
    # One CU process can serve several runner sessions; same clock, so older events are skipped.
    return [e for e in EVENT.iter_unpack(body) if e[0] >= since_ns]


def write_csv(events: list[tuple], path: Path) -> None:
    with Path(path).open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['t_ns', 'plan', 'item', 'value', 'kind'])
        writer.writerows(events)


def level_steps(delta: list[tuple], temp: list[tuple]) -> list[tuple]:
    """Step function of one operator: (time, outputs + temporaries, outputs only) after each event."""
    times = sorted({t for t, _ in delta} | {t for t, _ in temp})
    outputs = temporaries = i = j = 0
    steps = []
    for t in times:
        while i < len(delta) and delta[i][0] <= t:
            outputs += delta[i][1]
            i += 1
        while j < len(temp) and temp[j][0] <= t:
            temporaries = temp[j][1]
            j += 1
        steps.append((t, outputs + temporaries, outputs))
    return steps


def plan_timeline(steps_per_operator: list[list[tuple]], max_points: int = 2000) -> list[list[int]]:
    """Sum of all operators of one plan over time, thinned to at most max_points points."""
    changes = []
    for steps in steps_per_operator:
        previous = 0
        for t, total, _ in steps:
            changes.append((t, total - previous))
            previous = total
    level, points = 0, []
    for t, change in sorted(changes):
        level += change
        points.append([t, level])
    if len(points) > max_points:
        stride = -(-len(points) // max_points)
        points = points[::stride] + ([points[-1]] if (len(points) - 1) % stride else [])
    return points


def derive(events: list[tuple], plans: dict | None = None) -> dict:
    """Per-operator peak, integral and retained bytes plus a per-plan timeline."""
    plans = plans or {}
    dropped = sum(value for _, _, _, value, kind in events if kind == DROPPED)
    owners = defaultdict(lambda: {'delta': [], 'temp': []})
    for t, plan, item, value, kind in events:
        if kind == DELTA:
            owners[(plan, item)]['delta'].append((t, value))
        elif kind == TEMP:
            owners[(plan, item)]['temp'].append((t, value))
    operators, steps_by_plan = [], defaultdict(list)
    for (plan, item), owner in owners.items():
        steps = level_steps(sorted(owner['delta']), sorted(owner['temp']))
        if not steps:
            continue
        # Start and end snapshots of OperatorScope delimit the run, so no clock mapping is needed.
        start = min(t for t, _ in owner['temp']) if owner['temp'] else steps[0][0]
        end = max(t for t, _ in owner['temp']) if owner['temp'] else steps[0][0]
        # Step function: between two events the level is exact, so no interpolation.
        area = sum(a[1] * (b[0] - a[0]) for a, b in zip(steps, steps[1:])) / 1e9
        at_end = [s for s in steps if s[0] <= end]
        window = plans.get(plan, {})
        operators.append({
            'plan_id': plan, 'item': item,
            'query': window.get('query'), 'round': window.get('round'), 'warmup': window.get('warmup'),
            'start_ns': start, 'end_ns': end,
            'peak_bytes': max(s[1] for s in steps),
            'integral_mib_seconds': area / MIB,
            'retained_bytes': at_end[-1][2] if at_end else 0,       # outputs when the operator ended
            'live_bytes_at_plan_end': steps[-1][2],                 # outputs still live after the last event; 0 once freed
        })
        steps_by_plan[plan].append(steps)
    return {'events': len(events), 'events_dropped': dropped,
            'operators': sorted(operators, key=lambda r: (r['plan_id'], r['item'])),
            'plans': [{'plan_id': plan, 'timeline': plan_timeline(steps)}
                      for plan, steps in sorted(steps_by_plan.items())]}
