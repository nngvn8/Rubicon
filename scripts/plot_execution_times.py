#!/usr/bin/env python3
"""Compare per-query execution times stored in benchmark JSON files.

Each input must be a JSON object mapping plan-file names (for example,
``q1-1_1.pb``) to timing objects.  Files can only be compared when their
top-level key sets are identical.
"""

from __future__ import annotations

import argparse
import json
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

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    if not all(isinstance(query, str) and isinstance(result, dict)
               for query, result in data.items()):
        raise ValueError(
            f"{path} must map plan-file names to JSON objects containing timings."
        )
    return data


def query_label(plan_file: str) -> str:
    """Return the query name represented by a plan file name."""
    return plan_file.removesuffix(".pb")


def natural_query_key(plan_file: str) -> list[object]:
    """Sort names such as q2-10 after q2-9 while retaining arbitrary names."""
    import re

    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", query_label(plan_file))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", type=Path, nargs="*", metavar="RESULTS.json|DIRECTORY",
        help="benchmark JSON files or directories containing them (default: benchmarking)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("generated"),
        help="directory for the three output images (default: generated)",
    )
    parser.add_argument(
        "--title", default="Benchmark execution times", help="plot title",
    )
    return parser.parse_args()


def collect_files(inputs: list[Path]) -> list[Path]:
    """Expand directory inputs to their JSON files."""
    if not inputs:
        inputs = [Path("benchmarking")]

    files: list[Path] = []
    for input_path in inputs:
        if input_path.is_dir():
            files.extend(sorted(input_path.glob("*.json")))
        elif input_path.is_file():
            files.append(input_path)
        else:
            raise SystemExit(f"Input path does not exist: {input_path}")

    # Preserve input order while avoiding duplicates supplied both directly and
    # through a directory.
    return list(dict.fromkeys(files))


def main() -> None:
    args = parse_args()
    files = collect_files(args.inputs)
    if not files:
        raise SystemExit("No JSON files found in the specified input directory.")
    if len(files) < 2:
        raise SystemExit("Provide at least two JSON files to compare.")

    results = [(path, load_results(path)) for path in files]
    reference_path, reference = results[0]
    reference_keys = set(reference)
    for path, data in results[1:]:
        if set(data) != reference_keys:
            missing = sorted(reference_keys - set(data))
            extra = sorted(set(data) - reference_keys)
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if extra:
                details.append(f"extra: {', '.join(extra)}")
            raise SystemExit(
                f"Cannot compare {reference_path} and {path}: key sets differ "
                f"({' ; '.join(details)})."
            )

    queries = sorted(reference_keys, key=natural_query_key)
    fig_width = max(10, len(queries) * 0.55)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    labels = [query_label(query) for query in queries]

    for metric in METRICS:
        figure, axis = plt.subplots(figsize=(fig_width, 6))
        for path, data in results:
            try:
                times = [float(data[query][metric]) for query in queries]
            except (KeyError, TypeError, ValueError) as error:
                raise SystemExit(
                    f"{path} does not provide a numeric {metric} value for every query."
                ) from error
            axis.plot(labels, times, marker="o", label=path.stem)

        axis.set_title(f"{args.title}: {metric}")
        axis.set_xlabel("Query")
        axis.set_ylabel("Time (s)")
        axis.grid(axis="y", alpha=0.3)
        axis.legend(title="Benchmark")
        figure.tight_layout()
        output_path = args.output_dir / f"{metric}.png"
        figure.savefig(output_path, dpi=200)
        plt.close(figure)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
