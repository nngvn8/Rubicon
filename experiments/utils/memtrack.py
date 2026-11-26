"""Read the CU's per-operator memory log and derive occupancy numbers from it.

The log is written by computeUnit/src/infrastructure/MemTracker.cpp (RAM_TRACKING build):
a 32-byte header followed by raw 32-byte events. Values are requested capacity (virtual
memory attributed to the producing operator), not RSS.

Two routes for output buffers that are allocated for the worst case and shrunk later:
  A (as allocated): Alloc and Shrink at their own timestamps, shows the spike.
  B (net): each Shrink moves to the timestamp of its Alloc (same buf id), so the buffer
           counts as its final size from the start.
"""
from __future__ import annotations

import csv
import struct
from collections import defaultdict
from pathlib import Path

# Must match MemTracker.hpp: Event and FileHeader.
EVENT = struct.Struct('<QIIqB3xI')  # t_ns, plan, item, value, kind, buf
HEADER = struct.Struct('<8sIIQQ')   # magic, version, event_size, capacity, start_ns
MAGIC, VERSION = b'RUBIMEM1', 2
ALLOC, SHRINK, FREE, TEMP, DROPPED = 0, 1, 2, 3, 4  # value = +/- output bytes / absolute temp level / events lost
MIB = 1024 ** 2


def load_events(path: Path, since_ns: int = 0) -> list[tuple]:
    """Return (t_ns, plan, item, value, kind, buf) tuples that are not older than since_ns."""
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
        writer.writerow(['t_ns', 'plan', 'item', 'value', 'kind', 'buf'])
        writer.writerows(events)


def level_steps(delta: list[tuple], temp: list[tuple]) -> list[tuple]:
    """Step function of one operator: (time, outputs + temporaries, outputs only) after each event."""
    times = sorted({t for t, _ in delta} | {t for t, _ in temp})
    outputs = temporaries = i = j = 0
    steps = []
    # This also performs the sum for net, as net assigns alloc and shrink to the same timestamp
    for t in times:
        # Output events are deltas: add every event up to t.
        while i < len(delta) and delta[i][0] <= t:
            outputs += delta[i][1]
            i += 1
        # Temp events are absolute levels: the latest one up to t replaces the previous.
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
        # Turn each operator's levels back into changes, so operators can be summed on one time axis.
        for t, total, _ in steps:
            changes.append((t, total - previous))
            previous = total
    level, points = 0, []
    for t, change in sorted(changes):
        level += change
        points.append([t, level])
    if len(points) > max_points:
        # Ceiling division; the last point is kept so the timeline ends at the true final level.
        stride = -(-len(points) // max_points)
        points = points[::stride] + ([points[-1]] if (len(points) - 1) % stride else [])
    return points


def derive(events: list[tuple], plans: dict | None = None) -> dict:
    """Per-operator peak, integral and retained bytes plus a per-plan timeline, for route A and route B (*_net)."""
    plans = plans or {}
    # Events the CU could not store; levels are incomplete when this is above 0.
    dropped = sum(value for _, _, _, value, kind, _ in events if kind == DROPPED)
    # Buffer id -> time of its Alloc, used to move a Shrink back to its Alloc for route B.
    alloc_time = {buf: t for t, _, _, _, kind, buf in events if kind == ALLOC}
    # Per (plan, item): route A events (gross), route B events (net), temp snapshots.
    owners = defaultdict(lambda: {'gross': [], 'net': [], 'temp': []})
    unpaired_shrinks = 0
    # Fill gross, net, temp lists for each owner. Also count unpaired shrinks.
    for t, plan, item, value, kind, buf in events:
        if kind == DROPPED:
            continue  # carries plan 0 and item 0, which is not an operator
        if kind not in (ALLOC, SHRINK, FREE, TEMP):
            raise ValueError(f'unknown event kind {kind} at t={t}')
        owner = owners[(plan, item)]
        if kind == TEMP:
            owner['temp'].append((t, value))
            continue
        if kind == ALLOC and not buf:
            raise ValueError(f'Alloc event without buffer id (plan {plan}, item {item}, t={t})')
        owner['gross'].append((t, value))
        net_t = t
        if kind == SHRINK:
            if buf in alloc_time:
                net_t = alloc_time[buf]  # route B: the buffer counts as its final size from its Alloc on
            else:
                unpaired_shrinks += 1  # Alloc was dropped or is older than the session; keeps its own time
        owner['net'].append((net_t, value))
    operators, steps_by_plan, steps_net_by_plan = [], defaultdict(list), defaultdict(list)
    # Compute the actual step functions for each operator, as well as the integral.
    for (plan, item), owner in owners.items():
        if not owner['temp']:
            if dropped:
                continue  # the operator's start and end snapshots were among the dropped events
            raise ValueError(f'plan {plan}, item {item}: no TempLevel snapshots, the log is incomplete')
        # Events of one operator may come from several threads, so order them by time.
        temp = sorted(owner['temp'])
        steps = level_steps(sorted(owner['gross']), temp)
        steps_net = level_steps(sorted(owner['net']), temp)
        # Start and end snapshots of OperatorScope delimit the run, so no clock mapping is needed.
        start, end = temp[0][0], temp[-1][0]
        # Step function: between two events the level is exact, so no interpolation.
        area = sum(a[1] * (b[0] - a[0]) for a, b in zip(steps, steps[1:])) / 1e9
        area_net = sum(a[1] * (b[0] - a[0]) for a, b in zip(steps_net, steps_net[1:])) / 1e9
        at_end = [s for s in steps if s[0] <= end]  # includes the end snapshot, so never empty
        window = plans.get(plan, {})
        steps_by_plan[plan].append(steps)
        steps_net_by_plan[plan].append(steps_net)
        operators.append({
            'plan_id': plan, 'item': item,
            'query': window.get('query'), 'round': window.get('round'), 'warmup': window.get('warmup'),
            'start_ns': start, 'end_ns': end,
            'peak_bytes': max(s[1] for s in steps),
            'integral_mib_seconds': area / MIB,
            'peak_bytes_net': max(s[1] for s in steps_net),
            'integral_mib_seconds_net': area_net / MIB,
            'retained_bytes': at_end[-1][2],                        # outputs when the operator ended
            'live_bytes_at_plan_end': steps[-1][2],                 # outputs still live after the last event; 0 once freed
        })
    return {'events': len(events), 'events_dropped': dropped, 'unpaired_shrinks': unpaired_shrinks,
            'operators': sorted(operators, key=lambda r: (r['plan_id'], r['item'])),
            'plans': [{'plan_id': plan, 'timeline': plan_timeline(steps),
                       'timeline_net': plan_timeline(steps_net_by_plan[plan])}
                      for plan, steps in sorted(steps_by_plan.items())]}
