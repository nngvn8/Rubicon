#!/usr/bin/env python3
"""Render recorded CU memory after benchmarking, without changing the raw inputs.

Usage: python3 scripts/benchmark_plotting/plot_memory.py BENCHMARK_DIRECTORY
The input can also be results.json or memory_summary.json from that directory.
Runs recorded with --memtrack additionally get tracking_*.png: requested capacity per
plan and operator (virtual memory attributed to the producing operator), next to RSS.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from index import compact_variant
from plot_benchmarks import output_batch

MIB = 1024 ** 2
REPOSITORY = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPOSITORY / 'benchmarking/plots/memory'


def load_memory(path: Path) -> tuple[list[dict], dict, tuple[Path, ...]]:
    """Resolve one session's files and validate the sample order before rendering."""
    path = path.resolve()
    # A directory is convenient for manual use; results.json supports stored links.
    if path.is_dir():
        path = path / 'memory_summary.json'
    inputs = [path]
    if path.name == 'results.json':
        results = json.loads(path.read_text(encoding='utf-8'))
        links = results.get('memory')
        if not isinstance(links, dict) or not all(isinstance(links.get(k), str) for k in ('summary', 'samples')):
            raise ValueError('results.json does not link to memory collection artifacts')
        summary_path = path.parent / links['summary']
        samples_path = path.parent / links['samples']
        inputs.append(summary_path)
    else:
        summary_path = path
        samples_path = path.parent / 'memory_samples.csv'
    inputs.append(samples_path)

    # The plot consumes persisted IDs and clock mappings; it never re-guesses epochs.
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if (not isinstance(summary, dict) or not isinstance(summary.get('metadata'), dict)
            or not isinstance(summary.get('windows'), list) or not isinstance(summary.get('operators'), list)):
        raise ValueError('invalid memory summary: expected metadata, windows, and operators')
    baseline = summary['metadata'].get('baseline_bytes')
    if baseline is not None and (not isinstance(baseline, (int, float)) or not math.isfinite(baseline) or baseline < 0):
        raise ValueError('baseline_bytes must be nonnegative and finite, or null')

    samples = []
    with samples_path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        required = ('read_start_ns', 'read_end_ns', 'timestamp_ns', 'rss_bytes')
        if reader.fieldnames is None or not set(required) <= set(reader.fieldnames):
            raise ValueError('memory CSV is missing required sample columns')
        for line, row in enumerate(reader, start=2):
            # Keep times as integers: subtracting their origin later avoids float loss.
            try:
                sample = {key: int(row[key]) for key in required}
            except (TypeError, ValueError) as error:
                raise ValueError(f'invalid memory sample at CSV line {line}') from error
            if not sample['read_start_ns'] <= sample['timestamp_ns'] <= sample['read_end_ns'] or sample['rss_bytes'] < 0:
                raise ValueError(f'invalid sample timing or RSS at CSV line {line}')
            # Unsorted or duplicate timestamps would distort the displayed trajectory.
            if samples and sample['timestamp_ns'] <= samples[-1]['timestamp_ns']:
                raise ValueError('memory sample timestamps must increase strictly')
            samples.append(sample)
    if not samples:
        raise ValueError('memory trace contains no RSS samples')
    return samples, summary, tuple(inputs)


def render_memory(samples: list[dict], summary: dict):
    """Return an RSS timeline and execution lanes; intervals do not imply ownership."""
    origin = samples[0]['timestamp_ns']

    def seconds(timestamp_ns):
        # Shift before converting to seconds to retain small time differences.
        return (timestamp_ns - origin) / 1e9

    windows = summary['windows']
    plans = [w for w in windows if w['kind'] == 'plan' and 'end_ns' in w]
    # Reuse one lane per query so concurrent plans remain visible on a shared axis.
    queries = list(dict.fromkeys(w['query'] for w in plans))
    lane_by_query = {query: lane for lane, query in enumerate(queries)}
    metadata = summary['metadata']
    fig, (ram, lanes) = plt.subplots(2, 1, sharex=True, figsize=(14, 7),
                                     gridspec_kw={'height_ratios': [2, 1]})
    try:
        x, y = [], []
        max_gap_ns = metadata.get('max_gap_ms', float('inf')) * 1e6
        for index, sample in enumerate(samples):
            # Leave visible breaks where integration also considers coverage invalid.
            if index and sample['timestamp_ns'] - samples[index - 1]['timestamp_ns'] > max_gap_ns:
                x.append(float('nan'))
                y.append(float('nan'))
            x.append(seconds(sample['timestamp_ns']))
            y.append(sample['rss_bytes'] / MIB)
        ram.plot(x, y, linewidth=0.8)
        baseline = metadata.get('baseline_bytes')
        if baseline is not None:
            ram.axhline(baseline / MIB, color='gray', linestyle='--', label='Session baseline')
            ram.legend()
        for window in windows:
            # Round boundaries aid navigation without summing overlapping plan usage.
            if window['kind'] == 'round':
                ram.axvline(seconds(window['start_ns']), color='gray', alpha=0.25)
        for plan in plans:
            lane = lane_by_query[plan['query']]
            # Faded bars distinguish warmup; width is client submission-to-response time.
            duration = (plan['end_ns'] - plan['start_ns']) / 1e9
            lanes.broken_barh([(seconds(plan['start_ns']), duration)], (lane - 0.35, 0.7),
                             facecolors=f'C{lane % 10}', alpha=0.3 if plan['warmup'] else 0.7)
        for operator in summary['operators']:
            # Only aligned operators with a completed plan belong on this time axis.
            if operator['query'] not in lane_by_query:
                continue
            lane = lane_by_query[operator['query']]
            lanes.plot([seconds(operator['start_ns']), seconds(operator['end_ns'])],
                       [lane, lane], color='black', linewidth=0.6, alpha=0.5)
        source = metadata.get('source', 'unknown source')
        ram.set(ylabel='CU RSS (MiB)',
                title=f'Whole-CU resident memory ({source}; includes concurrent work)')
        lanes.set_yticks(range(len(queries)), queries, fontsize=7)
        lanes.set(xlabel='Seconds since first sample',
                  title='Plans by query; black segments: clock-aligned operators')
        if not plans:
            lanes.text(0.5, 0.5, 'No completed plan intervals', transform=lanes.transAxes, ha='center')
        fig.tight_layout()
        return fig
    except Exception:
        # Callers cannot close a figure that failed before being returned to them.
        plt.close(fig)
        raise


def natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]


def measured_plans(summary: dict) -> dict:
    """Completed plan windows of measured (non-warmup) rounds, by plan id."""
    return {w['plan_id']: w for w in summary['windows']
            if w['kind'] == 'plan' and not w['warmup'] and 'end_ns' in w}


def operator_names(summary: dict) -> dict:
    """Best effort: operator type per (query file, item id), read from the plan files."""
    try:
        sys.path.insert(0, str(REPOSITORY / 'experiments'))
        from proto import QueryPlan_pb2, WorkItem_pb2
    except ImportError:
        return {}
    names = {}
    for query in {w['query'] for w in summary['windows'] if w['kind'] == 'plan'}:
        for folder in ('data/pb_plans', 'data/plans'):
            path = REPOSITORY / folder / query
            if not path.is_file():
                continue
            try:
                plan = QueryPlan_pb2.QueryPlan.FromString(path.read_bytes())
                for item in plan.planitems:
                    names[(query, item.itemId)] = WorkItem_pb2.OperatorType.Name(item.operatorId).removeprefix('OP_')
            except Exception:  # labels are optional; ids still identify the operators
                pass
            break
    return names


def native_operators(summary: dict) -> dict:
    """Per-operator numbers sent by the CU (page faults, requested bytes), by (plan id, item id)."""
    return {(w['plan_id'], n['operator_id']): n for w in summary['windows'] if w['kind'] == 'plan'
            for n in w.get('native_operators', [])}


def step_sum(timelines: list, grid: np.ndarray) -> np.ndarray:
    """Add step functions given as [[t_ns, value], ...]: each value holds until the next point."""
    total = np.zeros(len(grid))
    for points in timelines:
        times = np.array([p[0] for p in points])
        values = np.array([p[1] for p in points], dtype=float)
        index = np.searchsorted(times, grid, side='right') - 1
        total += np.where(index >= 0, values[np.clip(index, 0, None)], 0.0)
    return total


def render_tracking_timeline(samples: list[dict], summary: dict, round_number: int | None = None):
    """RSS growth and tracked requested capacity of all plans of one measured round."""
    tracking = summary['operator_tracking']
    plans = measured_plans(summary)
    rounds = sorted({w['round'] for w in plans.values()})
    if not rounds:
        raise ValueError('no measured plans')
    # Round 1 is cold (fresh memory everywhere), so prefer the second round when there is one.
    round_number = round_number if round_number is not None else rounds[1 if len(rounds) > 1 else 0]
    in_round = {pid: w for pid, w in plans.items() if w['round'] == round_number}
    start = min(w['start_ns'] for w in in_round.values())
    end = max(w['end_ns'] for w in in_round.values())
    pad = int(0.5e9)
    timelines = [t['timeline'] for t in tracking['plans'] if t['plan_id'] in in_round and t['timeline']]
    grid = np.unique(np.concatenate([[start - pad, end + pad]] + [[p[0] for p in tl] for tl in timelines]))
    baseline = summary['metadata'].get('baseline_bytes') or samples[0]['rss_bytes']

    fig, ax = plt.subplots(figsize=(14, 6))
    try:
        rss = [(s['timestamp_ns'], s['rss_bytes']) for s in samples if start - pad <= s['timestamp_ns'] <= end + pad]
        ax.plot([(t - start) / 1e9 for t, _ in rss], [(r - baseline) / MIB for _, r in rss],
                color='C0', label='CU RSS above session baseline')
        ax.step((grid - start) / 1e9, step_sum(timelines, grid) / MIB, where='post',
                color='C3', label='Tracked requested capacity (outputs + temporaries, all plans)')
        # One dot per operator at its end: bytes it touched for the first time (page faults x 4 KiB).
        native = native_operators(summary)
        dots = [((o['end_ns'] - start) / 1e9, native[(o['plan_id'], o['item'])]['minor_faults'] * 4096 / MIB)
                for o in tracking['operators']
                if o['plan_id'] in in_round and native.get((o['plan_id'], o['item']), {}).get('minor_faults') is not None]
        ax.scatter([d[0] for d in dots], [d[1] for d in dots], s=14, color='black', alpha=0.6, zorder=3,
                   label='Touched by one operator (page faults x 4 KiB), at the end of the operator')
        for index, (pid, w) in enumerate(sorted(in_round.items(), key=lambda kv: kv[1]['start_ns'])):
            ax.axvspan((w['start_ns'] - start) / 1e9, (w['end_ns'] - start) / 1e9,
                       color=f'C{index % 10}', alpha=0.08)
            ax.text((w['start_ns'] - start) / 1e9, 1.01, w['query'].split('_')[0], transform=ax.get_xaxis_transform(),
                    fontsize=7, rotation=45, ha='left', va='bottom')
        mode = summary['metadata'].get('benchmark', {}).get('execution_mode', '')
        ax.set(xlabel='Seconds since the first submission of the round', ylabel='MiB',
               title=f'Measured round {round_number} ({mode}): tracked capacity vs. RSS growth\n')
        ax.set_ylim(top=ax.get_ylim()[1] * 1.25)  # headroom for the legend
        ax.legend(loc='upper left')
        fig.tight_layout()
        return fig
    except Exception:
        plt.close(fig)
        raise


def render_tracking_queries(samples: list[dict], summary: dict):
    """Per query: peak tracked capacity of a plan next to the RSS growth during that plan."""
    tracking = summary['operator_tracking']
    peaks = {t['plan_id']: max((p[1] for p in t['timeline']), default=0) for t in tracking['plans']}
    times = np.array([s['timestamp_ns'] for s in samples])
    rss = np.array([s['rss_bytes'] for s in samples], dtype=float)
    values = defaultdict(lambda: {'tracked': [], 'rss': []})
    for pid, w in measured_plans(summary).items():
        window = (times >= w['start_ns']) & (times <= w['end_ns'])
        # Memory left over from earlier plans is not growth of this one, so measure from the plan start.
        start_rss = rss[max(np.searchsorted(times, w['start_ns'], side='right') - 1, 0)]
        if pid in peaks and window.any():
            values[w['query']]['tracked'].append(peaks[pid] / MIB)
            values[w['query']]['rss'].append((rss[window].max() - start_rss) / MIB)
    if not values:
        raise ValueError('no measured plans with samples')
    queries = sorted(values, key=natural_key)
    x = np.arange(len(queries))
    fig, ax = plt.subplots(figsize=(14, 6))
    try:
        for offset, (key, label, color) in zip((-0.2, 0.2), (('tracked', 'Tracked peak requested capacity', 'C3'),
                                                           ('rss', 'RSS growth during the plan (peak minus RSS at plan start)', 'C0'))):
            medians = [statistics.median(values[q][key]) for q in queries]
            low = [m - min(values[q][key]) for m, q in zip(medians, queries)]
            high = [max(values[q][key]) - m for m, q in zip(medians, queries)]
            ax.bar(x + offset, medians, 0.4, yerr=[low, high], capsize=2, color=color, label=label)
        mode = summary['metadata'].get('benchmark', {}).get('execution_mode', '')
        note = '' if mode == 'sequential' else ' (concurrent: RSS includes overlapping plans)'
        ax.set_xticks(x, [q.split('_')[0] for q in queries], rotation=45, ha='right')
        ax.set(ylabel='MiB', title=f'Per query: median over rounds, bars show min to max{note}\n'
                                   'RSS growth is small when the allocator reuses memory freed by earlier plans')
        ax.set_ylim(top=ax.get_ylim()[1] * 1.25)  # headroom for the legend
        ax.legend(loc='upper left')
        fig.tight_layout()
        return fig
    except Exception:
        plt.close(fig)
        raise


def render_tracking_operators(samples: list[dict], summary: dict, top: int = 15):
    """The operators with the largest peak: requested, touched (page faults) and retained bytes."""
    plans = measured_plans(summary)
    native = native_operators(summary)
    groups = defaultdict(lambda: defaultdict(list))
    for o in summary['operator_tracking']['operators']:
        if o['plan_id'] not in plans:
            continue
        group, n = groups[(o['query'], o['item'])], native.get((o['plan_id'], o['item']), {})
        group['peak'].append(o['peak_bytes'] / MIB)
        group['retained'].append(o['retained_bytes'] / MIB)
        if n.get('requested_bytes') is not None:
            group['requested'].append(n['requested_bytes'] / MIB)
        if n.get('minor_faults') is not None:
            group['touched'].append(n['minor_faults'] * 4096 / MIB)
    if not groups:
        raise ValueError('no measured operators')
    ranked = sorted(groups.items(), key=lambda kv: -statistics.median(kv[1]['peak']))[:top][::-1]
    names = operator_names(summary)
    labels = [f"{query.split('_')[0]} #{item} {names.get((query, item), '')}".strip() for (query, item), _ in ranked]
    series = (('requested', 'Requested (output capacity)', 'C3'),
              ('touched', 'Touched (page faults x 4 KiB; includes temporaries)', 'C0'),
              ('retained', 'Retained after the operator (output, after shrink)', 'C2'),
              ('peak', 'Peak (outputs + temporaries)', 'C1'))
    y = np.arange(len(ranked))
    fig, ax = plt.subplots(figsize=(14, 0.55 * len(ranked) + 2.5))
    try:
        for index, (key, label, color) in enumerate(series):
            medians = [statistics.median(g[key]) if g[key] else 0 for _, g in ranked]
            ax.barh(y + (index - 1.5) * 0.2, medians, 0.2, color=color, label=label)
        ax.set_yticks(y, labels, fontsize=8)
        ax.set(xlabel='MiB (median over measured rounds)', title=f'Top {len(ranked)} operators by peak')
        ax.legend(loc='lower right', fontsize=8)
        fig.tight_layout()
        return fig
    except Exception:
        plt.close(fig)
        raise


TRACKING_FIGURES = (('tracking_timeline.png', render_tracking_timeline),
                    ('tracking_queries.png', render_tracking_queries),
                    ('tracking_operators.png', render_tracking_operators))

# Overview across queries and scale factors. The main metric is the footprint of a plan: the sum of
# the bytes its operators retain. Nothing is freed before the plan ends, so this is what the plan
# holds right before its tables are dropped, free of the worst-case over-allocation of the capacity.
METRICS = (('retained', 'Footprint (sum of retained output bytes)', 'C2'),
           ('touched', 'Touched (page faults x 4 KiB, includes temporaries)', 'C0'),
           ('peak', 'Peak requested capacity (upper bound)', 'C3'))


def query_label(name: str) -> str:
    match = re.match(r'q(\d+)-(\d+)', name)
    return f'Q{match[1]}.{match[2]}' if match else name


def plan_metrics(summary: dict) -> dict:
    """Median over the measured rounds of footprint, touched bytes and peak capacity, per query (MiB)."""
    tracking = summary['operator_tracking']
    plans = measured_plans(summary)
    native = native_operators(summary)
    peak = {t['plan_id']: max((p[1] for p in t['timeline']), default=0) for t in tracking['plans']}
    retained, touched = defaultdict(float), defaultdict(float)
    for o in tracking['operators']:
        retained[o['plan_id']] += o['retained_bytes']
    for (plan_id, _), n in native.items():
        touched[plan_id] += (n.get('minor_faults') or 0) * 4096
    per_query = defaultdict(lambda: defaultdict(list))
    for plan_id, w in plans.items():
        if plan_id in peak:
            per_query[w['query']]['retained'].append(retained[plan_id] / MIB)
            per_query[w['query']]['touched'].append(touched[plan_id] / MIB)
            per_query[w['query']]['peak'].append(peak[plan_id] / MIB)
    return {query: {key: statistics.median(values) for key, values in metrics.items()}
            for query, metrics in per_query.items()}


def load_overview_run(path: Path) -> tuple[str, int, dict]:
    path = Path(path).resolve()
    summary_path = path / 'memory_summary.json' if path.is_dir() else path.with_name('memory_summary.json')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if 'operator_tracking' not in summary:
        raise ValueError(f'{summary_path.parent.name}: no operator_tracking (run with --memtrack)')
    benchmark = summary['metadata'].get('benchmark', {})
    return benchmark['execution_mode'], int(benchmark['scale_factor']), plan_metrics(summary)


def render_overview(mode: str, runs: dict):
    """runs: {scale factor: {query: metrics}}. Absolute heatmap, absolute metric comparison, scaling."""
    scale_factors = sorted(runs)
    queries = sorted({q for metrics in runs.values() for q in metrics}, key=natural_key)
    labels = [query_label(q) for q in queries]
    y = np.arange(len(queries))
    fig, (heat, absolute, scaling) = plt.subplots(1, 3, figsize=(22, 0.6 * len(queries) + 3.5), sharey=True,
                                                  gridspec_kw={'width_ratios': [1.1, 1.3, 1.3]})
    try:
        # Panel 1: footprint per query and scale factor, with the absolute value in every cell.
        grid = np.array([[runs[sf].get(q, {}).get('retained', np.nan) for sf in scale_factors] for q in queries]) / 1024
        image = heat.imshow(grid, aspect='auto', cmap='Blues', norm=matplotlib.colors.LogNorm(
            vmin=np.nanmin(grid[grid > 0]) if (grid > 0).any() else 1e-3, vmax=np.nanmax(grid)))
        for row in range(len(queries)):
            for column in range(len(scale_factors)):
                value = grid[row, column]
                if np.isfinite(value):
                    dark = image.norm(value) > 0.55
                    heat.text(column, row, f'{value:.2f} GiB' if value >= 0.01 else f'{value * 1024:.1f} MiB',
                              ha='center', va='center', fontsize=9, color='white' if dark else 'black')
        heat.set_xticks(range(len(scale_factors)), [f'SF {sf}' for sf in scale_factors])
        heat.set_yticks(y, labels)
        heat.set_title('Footprint of a plan (absolute)', loc='left', fontweight='bold')
        heat.set_xlabel('Sum of the bytes the operators retain (median over rounds)')

        # Panel 2: the three metrics side by side at the largest scale factor (absolute, log axis).
        largest = scale_factors[-1]
        for offset, (key, label, color) in zip((-0.2, 0, 0.2), METRICS):
            values = [runs[largest].get(q, {}).get(key, np.nan) / 1024 for q in queries]
            absolute.scatter(values, y + offset, color=color, s=40, label=label, zorder=3)
        absolute.set_xscale('log')
        absolute.grid(axis='x', alpha=0.3)
        absolute.set_title(f'Metrics compared at SF {largest} (absolute)', loc='left', fontweight='bold')
        absolute.set_xlabel('GiB (log scale)')
        absolute.legend(loc='lower left', fontsize=8)

        # Panel 3: growth between the two largest scale factors; a ratio equal to the scale ratio is linear.
        if len(scale_factors) >= 2:
            low, high = scale_factors[-2], scale_factors[-1]
            for offset, (key, label, color) in zip((-0.2, 0, 0.2), METRICS):
                ratios = [runs[high].get(q, {}).get(key, np.nan) / runs[low].get(q, {}).get(key, np.nan)
                          if runs[low].get(q, {}).get(key) else np.nan for q in queries]
                scaling.scatter(ratios, y + offset, color=color, s=40, zorder=3)
            scaling.axvline(high / low, color='black', linestyle='--', label=f'Linear scaling ({high / low:g}x)')
            scaling.grid(axis='x', alpha=0.3)
            scaling.legend(loc='lower right', fontsize=8)
            scaling.set_title(f'Growth from SF {low} to SF {high} (relative)', loc='left', fontweight='bold')
            scaling.set_xlabel(f'Value at SF {high} / value at SF {low}')
        else:
            scaling.text(0.5, 0.5, 'Needs two scale factors', transform=scaling.transAxes, ha='center')
        heat.set_ylim(len(queries) - 0.5, -0.5)  # Q1.1 at the top, shared by all panels
        fig.suptitle(f'{mode.capitalize()} execution: memory of a query plan', fontsize=14, fontweight='bold')
        fig.tight_layout()
        return fig
    except Exception:
        plt.close(fig)
        raise


def export_overview(paths: list[Path], output_root: Path = OUTPUT_ROOT) -> Path:
    """One overview figure per execution mode from runs of several scale factors."""
    by_mode = defaultdict(dict)
    for path in paths:
        mode, scale_factor, metrics = load_overview_run(path)
        if scale_factor in by_mode[mode]:
            raise ValueError(f'two {mode} runs for SF {scale_factor}; pass one run per mode and scale factor')
        by_mode[mode][scale_factor] = metrics
    with output_batch(Path(output_root), description='overview') as (staging, final):
        figures = []
        for mode, runs in sorted(by_mode.items()):
            figure = render_overview(mode, runs)
            try:
                figure.savefig(staging / f'overview_{mode}.png', dpi=160)
                figures.append(f'overview_{mode}.png')
            finally:
                plt.close(figure)
        manifest = {'generated_at': datetime.now(timezone.utc).isoformat(), 'figures': figures,
                    'inputs': [str(Path(p).resolve()) for p in paths],
                    'metrics': [key for key, _, _ in METRICS]}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return final


def fingerprints(paths: tuple[Path, ...]) -> dict:
    """Record input content so exported figures can be traced to their measurements."""
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def batch_description(summary: dict, run_name: str) -> str:
    """Name a plot batch by mode, variant, scale factor and run so runs are told apart."""
    benchmark = summary['metadata'].get('benchmark', {})
    parts = [benchmark.get('execution_mode'),
             compact_variant(benchmark, Path(run_name)) if benchmark.get('variant') else None,
             f"sf{benchmark['scale_factor']}" if 'scale_factor' in benchmark else None,
             run_name.split('_')[0]]
    return '_'.join(part for part in parts if part)


def export_memory(path: Path, output_root: Path = OUTPUT_ROOT) -> Path:
    """Publish a new plot batch using the same atomic export helper as timing plots."""
    samples, summary, inputs = load_memory(path)
    before = fingerprints(inputs)
    # Reject a collector that is still writing while we load/render its trace.
    reloaded_samples, reloaded_summary, _ = load_memory(path)
    if samples != reloaded_samples or summary != reloaded_summary:
        raise ValueError('memory inputs changed during loading; wait for collection to finish')
    with output_batch(Path(output_root), description=batch_description(summary, inputs[0].parent.name)) as (staging, final):
        figure = render_memory(samples, summary)
        figures = ['memory.png']
        try:
            figure.savefig(staging / 'memory.png', dpi=160)
        finally:
            # Many sessions may be rendered in one Python process without leaking figures.
            plt.close(figure)
        if isinstance(summary.get('operator_tracking'), dict):
            for name, render in TRACKING_FIGURES:
                try:
                    figure = render(samples, summary)
                except ValueError as error:  # e.g. no measured plans: skip this figure only
                    print(f'Skipping {name}: {error}')
                    continue
                try:
                    figure.savefig(staging / name, dpi=160)
                    figures.append(name)
                finally:
                    plt.close(figure)
        if fingerprints(inputs) != before:
            raise ValueError('memory inputs changed during plotting; batch was not published')
        manifest = {'generated_at': datetime.now(timezone.utc).isoformat(),
                    'inputs': before, 'metadata': summary['metadata'], 'figures': figures,
                    'interpretation': summary.get('interpretation'),
                    'rendering_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, nargs='?',
                        help='Benchmark directory, results.json, or memory_summary.json')
    parser.add_argument('--overview', type=Path, nargs='+', metavar='DIR',
                        help='Overview across queries and scale factors from several benchmark directories '
                             '(one per execution mode and scale factor) instead of a single-run plot')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT_ROOT,
                        help='Parent directory for new plot batches (default: benchmarking/plots/memory)')
    args = parser.parse_args()
    if (args.input is None) == (args.overview is None):
        parser.error('pass either a benchmark directory or --overview DIR [DIR ...]')
    try:
        if args.overview:
            output = export_overview(args.overview, args.output_dir)
            print(f'Overview plots written to {output}')
            return
        output = export_memory(args.input, args.output_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f'Memory plot written to {output / "memory.png"}')


if __name__ == '__main__':
    main()
