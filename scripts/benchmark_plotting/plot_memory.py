#!/usr/bin/env python3
"""Render recorded CU memory after benchmarking, without changing the raw inputs.

Usage: python3 scripts/benchmark_plotting/plot_memory.py BENCHMARK_DIRECTORY
The input can also be results.json or memory_summary.json from that directory.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from plot_benchmarks import output_batch

MIB = 1024 ** 2
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / 'benchmarking/plots/memory'


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


def fingerprints(paths: tuple[Path, ...]) -> dict:
    """Record input content so exported figures can be traced to their measurements."""
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def export_memory(path: Path, output_root: Path = OUTPUT_ROOT) -> Path:
    """Publish a new plot batch using the same atomic export helper as timing plots."""
    samples, summary, inputs = load_memory(path)
    before = fingerprints(inputs)
    # Reject a collector that is still writing while we load/render its trace.
    reloaded_samples, reloaded_summary, _ = load_memory(path)
    if samples != reloaded_samples or summary != reloaded_summary:
        raise ValueError('memory inputs changed during loading; wait for collection to finish')
    with output_batch(Path(output_root), description=inputs[0].parent.name) as (staging, final):
        figure = render_memory(samples, summary)
        try:
            figure.savefig(staging / 'memory.png', dpi=160)
        finally:
            # Many sessions may be rendered in one Python process without leaking figures.
            plt.close(figure)
        if fingerprints(inputs) != before:
            raise ValueError('memory inputs changed during plotting; batch was not published')
        manifest = {'generated_at': datetime.now(timezone.utc).isoformat(),
                    'inputs': before, 'metadata': summary['metadata'], 'figures': ['memory.png'],
                    'interpretation': summary.get('interpretation'),
                    'rendering_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Benchmark directory, results.json, or memory_summary.json')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT_ROOT,
                        help='Parent directory for new plot batches (default: benchmarking/plots/memory)')
    args = parser.parse_args()
    try:
        output = export_memory(args.input, args.output_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f'Memory plot written to {output / "memory.png"}')


if __name__ == '__main__':
    main()
