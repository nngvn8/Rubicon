#!/usr/bin/env python3
"""Render recorded CU memory after benchmarking, without changing the raw inputs.

Usage: python3 scripts/benchmark_plotting/plot_memory.py BENCHMARK_DIRECTORY
The input can also be results.json or memory_summary.json from that directory.
Also: --cross-scale DIR... writes memory/cross_scale_{peak,integral,average}.png (merged vs non-merged).
Writes memory/round_1.png, round_2.png, mean_rounds_2-N.png and all_rounds.png: CU RSS above the
session baseline, and for --memtrack runs the tracked requested capacity, above the plans per query.
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

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from index import compact_variant
from plot_benchmarks import output_batch

MIB = 1024 ** 2
GRID_S = 0.02  # RSS sampling interval
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
            or not isinstance(summary.get('plans'), list)):
        raise ValueError('invalid memory summary: expected metadata and plans')
    baseline = summary['metadata'].get('baseline_bytes')
    if baseline is not None and (not isinstance(baseline, (int, float)) or not math.isfinite(baseline) or baseline < 0):
        raise ValueError('baseline_bytes must be nonnegative and finite, or null')

    samples = []
    with samples_path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        required = ('timestamp_ns', 'rss_bytes')
        if reader.fieldnames is None or not set(required) <= set(reader.fieldnames):
            raise ValueError('memory CSV is missing required sample columns')
        for line, row in enumerate(reader, start=2):
            # Keep times as integers: subtracting their origin later avoids float loss.
            try:
                sample = {key: int(row[key]) for key in required}
            except (TypeError, ValueError) as error:
                raise ValueError(f'invalid memory sample at CSV line {line}') from error
            if sample['rss_bytes'] < 0:
                raise ValueError(f'invalid RSS at CSV line {line}')
            # Unsorted or duplicate timestamps would distort the displayed trajectory.
            if samples and sample['timestamp_ns'] <= samples[-1]['timestamp_ns']:
                raise ValueError('memory sample timestamps must increase strictly')
            samples.append(sample)
    if not samples:
        raise ValueError('memory trace contains no RSS samples')
    return samples, summary, tuple(inputs)


def natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', name)]


def measured_plans(summary: dict) -> dict:
    """Completed plan windows of measured (non-warmup) rounds, by plan id."""
    return {w['plan_id']: w for w in summary['plans'] if not w['warmup'] and 'end_ns' in w}


def step_sum(timelines: list, grid: np.ndarray) -> np.ndarray:
    """Add step functions given as [[t_ns, value], ...]: each value holds until the next point."""
    total = np.zeros(len(grid))
    for points in timelines:
        times = np.array([p[0] for p in points])
        values = np.array([p[1] for p in points], dtype=float)
        index = np.searchsorted(times, grid, side='right') - 1
        total += np.where(index >= 0, values[np.clip(index, 0, None)], 0.0)
    return total


def build_trace(samples: list[dict], summary: dict, plans: dict, start_ns: int, end_ns: int,
                pad_ns: int = int(0.5e9)) -> dict:
    """RSS above baseline and tracked capacity on the sample times of [start_ns - pad, end_ns + pad]."""
    baseline = summary['metadata'].get('baseline_bytes') or samples[0]['rss_bytes']
    times = np.array([s['timestamp_ns'] for s in samples])
    rss = np.array([s['rss_bytes'] for s in samples], dtype=float)
    keep = (times >= start_ns - pad_ns) & (times <= end_ns + pad_ns)
    grid = times[keep]
    tracked_plans = summary.get('operator_tracking', {}).get('plans', [])
    timelines = [t['timeline'] for t in tracked_plans if t['plan_id'] in plans and t['timeline']]
    # Sessions recorded before buffer ids were logged have no net timeline.
    timelines_net = [t['timeline_net'] for t in tracked_plans if t['plan_id'] in plans and t.get('timeline_net')]

    def seconds(ns):
        return (ns - start_ns) / 1e9

    return {'t': seconds(grid), 'rss': (rss[keep] - baseline) / MIB,
            'tracked': step_sum(timelines, grid) / MIB if timelines else None,
            'tracked_net': step_sum(timelines_net, grid) / MIB if timelines_net else None,
            'plans': [(w['query'], seconds(w['start_ns']), seconds(w['end_ns']), w['warmup'])
                      for w in plans.values()],
            'operators': [(o['query'], seconds(o['start_ns']), seconds(o['end_ns']))
                          for o in summary.get('operator_tracking', {}).get('operators', []) if o['plan_id'] in plans]}


def round_trace(samples: list[dict], summary: dict, round_number: int) -> dict:
    plans = {pid: w for pid, w in measured_plans(summary).items() if w['round'] == round_number}
    if not plans:
        raise ValueError(f'no measured plans in round {round_number}')
    return build_trace(samples, summary, plans, min(w['start_ns'] for w in plans.values()),
                       max(w['end_ns'] for w in plans.values()))


def all_rounds_trace(samples: list[dict], summary: dict) -> dict:
    plans = {w['plan_id']: w for w in summary['plans'] if 'end_ns' in w}
    return build_trace(samples, summary, plans, samples[0]['timestamp_ns'], samples[-1]['timestamp_ns'], 0)


def mean_trace(samples: list[dict], summary: dict, first_round: int = 2) -> dict:
    """Mean over rounds first_round..N after warping every round onto the mean plan boundaries."""
    plans = measured_plans(summary)
    rounds = sorted({w['round'] for w in plans.values() if w['round'] >= first_round})
    if not rounds:
        raise ValueError(f'no measured rounds from round {first_round}')
    sequential = summary['metadata'].get('benchmark', {}).get('execution_mode') == 'sequential'
    traces, anchors = [], []
    for number in rounds:
        trace = round_trace(samples, summary, number)
        # Plans overlap in concurrent mode, so only the round boundaries are anchors there.
        edges = sorted(t for _, s, e, _ in trace['plans'] for t in (s, e)) if sequential else []
        anchors.append([trace['t'][0], *edges, trace['t'][-1]])
        traces.append(trace)
    if len({len(a) for a in anchors}) != 1:
        raise ValueError('rounds have different numbers of plans; cannot align them')
    mean_anchors = np.mean(anchors, axis=0)
    axis = np.arange(mean_anchors[0], mean_anchors[-1], GRID_S)
    rss, tracked, tracked_net = [], [], []
    for trace, own in zip(traces, anchors):
        warped = np.interp(trace['t'], own, mean_anchors)
        rss.append(np.interp(axis, warped, trace['rss']))
        if trace['tracked'] is not None:
            tracked.append(np.interp(axis, warped, trace['tracked']))
        if trace['tracked_net'] is not None:
            tracked_net.append(np.interp(axis, warped, trace['tracked_net']))
    rss = np.array(rss)
    # Plan bars sit between the mean anchors; sorting by start pairs them with the sorted anchors.
    queries = [q for q, *_ in sorted(traces[0]['plans'], key=lambda p: p[1])] if sequential else []
    edges = mean_anchors[1:-1].reshape(-1, 2) if sequential else np.empty((0, 2))
    return {'t': axis, 'rss': rss.mean(axis=0), 'rss_band': (rss.min(axis=0), rss.max(axis=0)),
            'tracked': np.mean(tracked, axis=0) if tracked else None,
            'tracked_net': np.mean(tracked_net, axis=0) if tracked_net else None,
            'plans': [(q, s, e, False) for q, (s, e) in zip(queries, edges)], 'operators': []}


def render_memory(trace: dict, title: str, max_gap_s: float = 0.1, stacked: bool = False):
    """Top: RSS above baseline and tracked capacity (gross and net), in one panel or, if stacked,
    in one panel each with a shared y axis. Bottom: plans per query (lanes chart)."""
    queries = list(dict.fromkeys(q for q, *_ in trace['plans']))
    lane_by_query = {q: i for i, q in enumerate(queries)}
    t, rss, tracked, tracked_net = trace['t'], trace['rss'], trace['tracked'], trace['tracked_net']
    series = [('CU RSS above session baseline', 'C0'),
              ('Tracked requested capacity, gross (as allocated; outputs + temporaries, all plans)', 'C3'),
              ('Tracked requested capacity, net (outputs at final size from allocation)', 'C2')]
    present = [(label, color, values) for (label, color), values in zip(series, (rss, tracked, tracked_net))
               if values is not None]
    panels = len(present) if stacked else 1
    fig, axes = plt.subplots(panels + 1, 1, sharex=True, figsize=(14, 4 + 2.5 * panels),
                             gridspec_kw={'height_ratios': [2] * panels + [1 if panels == 1 else 2]})
    *tops, lanes = axes
    for extra in tops[1:]:
        extra.sharey(tops[0])
    try:
        # Break the curves where the sampling had a gap.
        cut = np.where(np.diff(t) > max_gap_s)[0] + 1

        def with_gaps(values):
            return np.insert(values, cut, np.nan)

        for i, (label, color, values) in enumerate(present):
            top = tops[i if stacked else 0]
            if values is rss:
                top.plot(with_gaps(t), with_gaps(rss), color=color, linewidth=0.8, label=label)
                if 'rss_band' in trace:
                    top.fill_between(t, *trace['rss_band'], color=color, alpha=0.15,
                                     label='RSS min to max over rounds')
            else:
                top.step(t, values, where='post', color=color, linewidth=0.8, label=label)
        for top in tops:
            top.set(ylabel='MiB')
            top.legend(loc='upper left')
        tops[0].set_title(title)
        for query, start, end, warmup in trace['plans']:
            lane = lane_by_query[query]
            # Faded bars distinguish warmup; width is client submission-to-response time.
            lanes.broken_barh([(start, end - start)], (lane - 0.35, 0.7),
                              facecolors=f'C{lane % 10}', alpha=0.3 if warmup else 0.7)
        for query, start, end in trace['operators']:
            if query in lane_by_query:
                lanes.plot([start, end], [lane_by_query[query]] * 2, color='black', linewidth=0.6, alpha=0.5)
        lanes.set_yticks(range(len(queries)), queries, fontsize=7)
        lanes.set(xlabel='Seconds', title='Plans by query; black segments: operators (--memtrack)')
        if not trace['plans']:
            lanes.text(0.5, 0.5, 'No completed plan intervals', transform=lanes.transAxes, ha='center')
        fig.tight_layout()
        return fig
    except Exception:
        # Callers cannot close a figure that failed before being returned to them.
        plt.close(fig)
        raise


def memory_views(samples: list[dict], summary: dict) -> dict:
    """File name -> (trace builder, title) for the four chart versions."""
    mode = summary['metadata'].get('benchmark', {}).get('execution_mode', '')
    last = max((w['round'] for w in measured_plans(summary).values()), default=0)
    return {
        'round_1.png': (lambda: round_trace(samples, summary, 1), f'Measured round 1 ({mode})'),
        'round_2.png': (lambda: round_trace(samples, summary, 2), f'Measured round 2 ({mode})'),
        f'mean_rounds_2-{last}.png': (lambda: mean_trace(samples, summary, 2),
                                     f'Mean of measured rounds 2..{last} ({mode}), aligned on plan boundaries'),
        'all_rounds.png': (lambda: all_rounds_trace(samples, summary), f'All rounds ({mode})'),
    }

# Overview across queries and scale factors. The main metric is the footprint of a plan: the sum of
# the bytes its operators retain. Nothing is freed before the plan ends, so this is what the plan
# holds right before its tables are dropped, free of the worst-case over-allocation of the capacity.
METRICS = (('retained', 'Footprint (sum of retained output bytes)', 'C2'),
           ('peak', 'Peak requested capacity (upper bound)', 'C3'))


def query_label(name: str) -> str:
    match = re.match(r'q(\d+)-(\d+)', name)
    return f'Q{match[1]}.{match[2]}' if match else name


def plan_metrics(summary: dict) -> dict:
    """Median over the measured rounds of footprint and peak capacity, per query (MiB)."""
    tracking = summary['operator_tracking']
    plans = measured_plans(summary)
    peak = {t['plan_id']: max((p[1] for p in t['timeline']), default=0) for t in tracking['plans']}
    retained = defaultdict(float)
    for o in tracking['operators']:
        retained[o['plan_id']] += o['retained_bytes']
    per_query = defaultdict(lambda: defaultdict(list))
    for plan_id, w in plans.items():
        if plan_id in peak:
            per_query[w['query']]['retained'].append(retained[plan_id] / MIB)
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

        # Panel 2: both metrics side by side at the largest scale factor (absolute, log axis).
        largest = scale_factors[-1]
        offsets = np.linspace(-0.15, 0.15, len(METRICS))
        for offset, (key, label, color) in zip(offsets, METRICS):
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
            for offset, (key, label, color) in zip(offsets, METRICS):
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


# Cross-scale comparison of merged against non-merged materialization, one figure per metric.
CROSS_METRICS = {
    'peak': ('Peak net tracked memory', 'peak of the plan'),
    'integral': ('Net tracked memory integral', 'integral over the plan window'),
    'average': ('Average net tracked memory', 'integral / plan duration'),
}


def plan_cross_metrics(summary: dict) -> dict:
    """Median over the measured rounds of peak, integral and average of the net tracked curve, per query.

    Units: MiB, MiB*s, MiB. The integral covers the plan window only, because outputs that are still
    live after the last event would otherwise extend the step function without bound.
    """
    plans = measured_plans(summary)
    per_query = defaultdict(lambda: defaultdict(list))
    for tracked in summary['operator_tracking']['plans']:
        window = plans.get(tracked['plan_id'])
        if window is None or not tracked.get('timeline_net'):
            continue
        times = np.array([p[0] for p in tracked['timeline_net']], dtype=float)
        levels = np.array([p[1] for p in tracked['timeline_net']], dtype=float)
        # Each level holds until the next point; the last one holds until the window ends.
        edges = np.clip(np.append(times, max(times[-1], window['end_ns'])), window['start_ns'], window['end_ns'])
        integral = float((levels * np.diff(edges)).sum()) / 1e9 / MIB
        per_query[window['query']]['peak'].append(levels.max() / MIB)
        per_query[window['query']]['integral'].append(integral)
        per_query[window['query']]['average'].append(integral / ((window['end_ns'] - window['start_ns']) / 1e9))
    return {query: {key: statistics.median(values) for key, values in metrics.items()}
            for query, metrics in per_query.items()}


def load_cross_scale_run(path: Path) -> tuple[str, bool, int, dict, Path]:
    """(execution mode, merged?, scale factor, per-query metrics, summary file) of one benchmark directory."""
    path = Path(path).resolve()
    summary_path = path / 'memory_summary.json' if path.is_dir() else path.with_name('memory_summary.json')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    name = summary_path.parent.name
    if 'plans' not in summary or not any('timeline_net' in t for t in summary.get('operator_tracking', {}).get('plans', [])):
        raise ValueError(f'{name}: no net timeline (run with a --memtrack build that logs buffer ids)')
    benchmark = summary['metadata'].get('benchmark', {})
    merged = benchmark.get('variant', {}).get('materialize_into_join')
    if not isinstance(merged, bool):
        raise ValueError(f'{name}: variant materialize_into_join is not recorded')
    return benchmark['execution_mode'], merged, int(benchmark['scale_factor']), plan_cross_metrics(summary), summary_path


def deviation_matrix(runs: dict, queries: list[str], scale_factors: list[int], key: str) -> np.ndarray:
    """100 * (merged / non-merged - 1) per query (rows) and scale factor (columns); NaN without a positive baseline."""
    matrix = np.full((len(queries), len(scale_factors)), np.nan)
    for column, sf in enumerate(scale_factors):
        for row, query in enumerate(queries):
            base = runs[False][sf].get(query, {}).get(key)
            merged = runs[True][sf].get(query, {}).get(key)
            if base and merged is not None:
                matrix[row, column] = 100 * (merged / base - 1)
    return matrix


def render_cross_scale(key: str, runs_by_mode: dict, queries: list[str], limits=(-20, 20)):
    """Two matrices (sequential left, concurrent right): query by scale factor, deviation in percent."""
    from matplotlib.colors import TwoSlopeNorm
    title, definition = CROSS_METRICS[key]
    lower, upper = limits
    modes = [m for m in ('sequential', 'concurrent') if m in runs_by_mode]
    cmap = plt.get_cmap('RdBu_r').copy()
    cmap.set_bad('#eeeeee')
    fig, axes = plt.subplots(1, len(modes), figsize=(5.5 * len(modes) + 1.5, max(5, 0.48 * len(queries) + 2.5)),
                             sharey=True, squeeze=False)
    try:
        axes = axes[0]
        for ax, mode in zip(axes, modes):
            runs = runs_by_mode[mode]
            scale_factors = sorted(runs[False])
            matrix = deviation_matrix(runs, queries, scale_factors, key)
            image = ax.imshow(np.ma.masked_invalid(matrix), aspect='auto', cmap=cmap,
                              norm=TwoSlopeNorm(vmin=lower, vcenter=0, vmax=upper))
            ax.set_xticks(range(len(scale_factors)), [f'SF {sf}' for sf in scale_factors])
            ax.set_yticks(range(len(queries)), [q.removesuffix('.pb') for q in queries])
            for row in range(len(queries)):
                for column in range(len(scale_factors)):
                    value = matrix[row, column]
                    ax.text(column, row, f'{value:+.1f}%' if np.isfinite(value) else 'N/A', ha='center', va='center',
                            color='white' if np.isfinite(value) and (value > 0.6 * upper or value < 0.6 * lower)
                            else '#17212b')
            ax.set_title(mode.capitalize())
        fig.colorbar(image, ax=list(axes), fraction=0.03, pad=0.02, extend='both').set_label(
            'Deviation (%) · colors clipped at limits')
        fig.suptitle(f'{title}: merged vs non-merged materialization (median over rounds; {definition})\n'
                     'Negative (blue) = merged uses less; positive (red) = merged uses more')
        return fig
    except Exception:
        plt.close(fig)
        raise


def export_cross_scale(paths: list[Path], output_root: Path = OUTPUT_ROOT, limits=(-20, 20)) -> Path:
    """One figure per metric from runs of both materialization variants, execution modes and scale factors."""
    runs_by_mode = defaultdict(lambda: {False: {}, True: {}})
    files = []
    for path in paths:
        mode, merged, scale_factor, metrics, summary_path = load_cross_scale_run(path)
        if scale_factor in runs_by_mode[mode][merged]:
            raise ValueError(f'two {mode} runs for SF {scale_factor} and the same variant; pass one run per combination')
        runs_by_mode[mode][merged][scale_factor] = metrics
        files.append(summary_path)
    for mode, runs in runs_by_mode.items():
        if sorted(runs[False]) != sorted(runs[True]) or not runs[False]:
            raise ValueError(f'{mode}: merged and non-merged runs must cover the same scale factors')
    queries = sorted({q for runs in runs_by_mode.values() for variant in runs.values()
                      for metrics in variant.values() for q in metrics}, key=natural_key)
    with output_batch(Path(output_root), description='cross-scale') as (staging, final):
        folder = staging / 'memory'
        folder.mkdir()
        figures = []
        for key in CROSS_METRICS:
            figure = render_cross_scale(key, runs_by_mode, queries, limits)
            try:
                figure.savefig(folder / f'cross_scale_{key}.png', dpi=160, bbox_inches='tight')
                figures.append(f'memory/cross_scale_{key}.png')
            finally:
                plt.close(figure)
        manifest = {'generated_at': datetime.now(timezone.utc).isoformat(), 'figures': figures,
                    'inputs': fingerprints(tuple(files)), 'queries': queries, 'color_limits': list(limits),
                    'statistic': '100 * (median over measured rounds, merged / median over measured rounds, non-merged - 1)',
                    'metrics': {key: {'label': label, 'definition': definition}
                                for key, (label, definition) in CROSS_METRICS.items()},
                    'curve': 'operator_tracking.plans[].timeline_net (requested capacity, virtual, not RSS)',
                    'rendering_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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
        folder = staging / 'memory'
        folder.mkdir()
        figures = []
        for name, (build, title) in memory_views(samples, summary).items():
            try:
                figure = render_memory(build(), title, summary['metadata'].get('max_gap_ms', float('inf')) / 1e3,
                                       stacked=name == 'all_rounds.png')
            except ValueError as error:  # e.g. fewer than two rounds: skip this version only
                print(f'Skipping {name}: {error}')
                continue
            try:
                figure.savefig(folder / name, dpi=160)
                figures.append(f'memory/{name}')
            finally:
                # Many sessions may be rendered in one Python process without leaking figures.
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
    parser.add_argument('--cross-scale', type=Path, nargs='+', metavar='DIR',
                        help='Merged vs non-merged deviation matrices (peak, integral, average) from benchmark '
                             'directories covering both variants, both execution modes and several scale factors')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT_ROOT,
                        help='Parent directory for new plot batches (default: benchmarking/plots/memory)')
    args = parser.parse_args()
    if sum(x is not None for x in (args.input, args.overview, args.cross_scale)) != 1:
        parser.error('pass either a benchmark directory, --overview DIR [DIR ...] or --cross-scale DIR [DIR ...]')
    try:
        if args.cross_scale:
            output = export_cross_scale(args.cross_scale, args.output_dir)
            print(f'Cross-scale plots written to {output / "memory"}')
            return
        if args.overview:
            output = export_overview(args.overview, args.output_dir)
            print(f'Overview plots written to {output}')
            return
        output = export_memory(args.input, args.output_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(f'Memory plots written to {output / "memory"}')


if __name__ == '__main__':
    main()
