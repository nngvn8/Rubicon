#!/usr/bin/env python3
"""Plot the per-query execution-time change of a merged benchmark.

With two positional files, the first is the baseline and the second is the
comparison result.  With no positional files, one JSON file whose name
contains ``merg`` and one whose name does not are selected from
``benchmarking/``.

Limitations:
    Automatic selection is arbitrary when there are several matching merged
    or non-merged result files.  It is intended only as a convenience for the
    current two-file setup; a later version may select files by a shared prefix.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


METRICS = ("operator_work", "plan_duration", "total_response_time")


def load_results(path: Path) -> dict[str, dict[str, Any]]:
    """Load one benchmark result file and validate its top-level structure."""
    try:
        with path.open(encoding="utf-8") as result_file:
            data = json.load(result_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load JSON from {path}: {error}") from error

    if not isinstance(data, dict) or not all(
        isinstance(query, str) and isinstance(result, dict)
        for query, result in data.items()
    ):
        raise ValueError(f"{path} must map plan-file names to timing objects.")
    return data


def query_label(plan_file: str) -> str:
    """Derive a query label from a plan-file name."""
    return plan_file.removesuffix(".pb")


def natural_query_key(plan_file: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", query_label(plan_file))]


def format_duration(value: float) -> str:
    """Format a duration compactly with three significant digits."""
    for scale, unit in ((1, "s"), (1e-3, "ms"), (1e-6, "µs"), (1e-9, "ns")):
        if abs(value) >= scale:
            return f"{value / scale:.3g}{unit}"
    return "0s"


def choose_default_files() -> tuple[Path, Path]:
    """Pick one non-merged and one merged JSON file from benchmarking/."""
    candidates = sorted(Path("benchmarking").glob("*.json"))
    merged = [path for path in candidates if "merg" in path.name.lower()]
    non_merged = [path for path in candidates if "merg" not in path.name.lower()]
    if not merged or not non_merged:
        raise SystemExit(
            "benchmarking/ must contain at least one merged and one non-merged JSON file."
        )
    return non_merged[0], merged[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files", type=Path, nargs="*", metavar="RESULTS.json",
        help="baseline JSON followed by the merged/comparison JSON",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("generated"),
        help="directory for the three output images (default: generated)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.files:
        baseline_path, comparison_path = choose_default_files()
    elif len(args.files) == 2:
        baseline_path, comparison_path = args.files
    else:
        raise SystemExit("Provide exactly two JSON files, or provide no files.")

    baseline = load_results(baseline_path)
    comparison = load_results(comparison_path)
    if set(baseline) != set(comparison):
        raise SystemExit("Cannot compare files: their top-level key sets differ.")

    queries = sorted(baseline, key=natural_query_key)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    labels = [query_label(query) for query in queries]
    for metric in METRICS:
        try:
            absolute_differences = [
                float(comparison[query][metric]) - float(baseline[query][metric])
                for query in queries
            ]
            percentages = [
                (float(comparison[query][metric]) - float(baseline[query][metric]))
                / float(baseline[query][metric]) * 100
                for query in queries
            ]
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise SystemExit(
                f"Both files must provide non-zero numeric {metric} values for every query."
            ) from error

        figure, axis = plt.subplots(figsize=(max(10, len(queries) * 0.55), 6))
        colors = ["tab:red" if value > 0 else "tab:green" for value in percentages]
        bars = axis.bar(labels, percentages, color=colors)
        for bar, difference in zip(bars, absolute_differences):
            offset = 3 if difference >= 0 else -3
            vertical_alignment = "bottom" if difference >= 0 else "top"
            axis.annotate(
                format_duration(difference),
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
                va=vertical_alignment,
            )
        axis.axhline(0, color="black", linewidth=1)
        axis.set_title(f"Merged vs. non-merged {metric}")
        axis.set_xlabel("Query")
        axis.set_ylabel("Time change relative to non-merged (%)")
        axis.grid(axis="y", alpha=0.3)
        figure.tight_layout()

        output_path = args.output_dir / f"merged_{metric}_difference.png"
        figure.savefig(output_path, dpi=200)
        plt.close(figure)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
