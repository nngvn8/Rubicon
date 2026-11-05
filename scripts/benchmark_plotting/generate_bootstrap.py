#!/usr/bin/env python3
"""Generate exploratory bootstrap charts for every compatible merged/unmerged pair.

Run from the repository root:
    python3 scripts/benchmark_plotting/generate_bootstrap.py
Use --inventory-only to inspect the proposed pairs without rendering anything.

A directory is an execution, not an independent replication of each round.
This driver never pairs round numbers across separately executed variants.
"""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime, timezone
import html
import itertools
import json
import os
from pathlib import Path

from data import METRICS
from index import write_index
from plot_benchmarks import OUTPUT_ROOT, read_config, render_pair

REPOSITORY = Path(__file__).resolve().parents[2]


def matching_settings(metadata):
    """Keep all recorded settings except timestamps, prose, and the tested switch.

    Keeping unknown metadata fields is deliberate: new configuration differences
    should split groups rather than silently create an invalid comparison.
    """
    settings = copy.deepcopy(metadata)
    for field in ("created_at", "experiment"):
        settings.pop(field, None)
    for field in ("optimization", "variant"):
        if isinstance(settings.get(field), dict):
            settings[field].pop("materialize_into_join", None)
    return settings


def discover_pairs(data_root):
    """Return all compatible cross-variant pairs; do not pool repeated executions."""
    groups, excluded, eligible = {}, [], []
    for path in sorted(data_root.rglob("results.json")):
        relative = path.relative_to(data_root)
        if relative.parts[0] == "bootstrap":
            continue  # Derived outputs must never become benchmark inputs.
        if "archive" in relative.parts or "-O0" in relative.parts:
            excluded.append({"directory": str(path.parent), "reason": "archive or -O0"})
            continue
        metadata = json.loads(path.read_text(encoding="utf-8"))["metadata"]
        if metadata.get("compilation", {}).get("optimization_level") == "-O0":
            excluded.append({"directory": str(path.parent), "reason": "metadata specifies -O0"})
            continue
        merged = metadata.get("optimization", {}).get("materialize_into_join")
        variant = metadata.get("variant", {}).get("materialize_into_join", merged)
        if type(merged) is not bool or variant != merged:
            raise ValueError(f"Missing or inconsistent merge setting: {path}")
        for field in ("scale_factor", "execution_mode"):
            if field not in metadata:
                raise ValueError(f"Missing matching field {field}: {path}")
        # execution_mode records sequential vs concurrent in these datasets.
        # If future data adds a separate concurrency setting, it is also kept.
        settings = matching_settings(metadata)
        key = json.dumps(settings, sort_keys=True)
        group = groups.setdefault(key, {"settings": settings, False: [], True: []})
        group[merged].append(path.parent)
        eligible.append(str(path.parent))
    pairs, unmatched = [], []
    for group in groups.values():
        if not group[False] or not group[True]:
            unmatched.extend(str(p) for merged in (False, True) for p in group[merged])
        for baseline, comparison in itertools.product(group[False], group[True]):
            pairs.append({"baseline": str(baseline), "comparison": str(comparison),
                          "matching_settings": group["settings"]})
    return {"eligible_directories": eligible, "excluded": excluded,
            "unmatched_directories": unmatched, "pairs": pairs,
            "pairing_policy": "All compatible unmerged-to-merged directory pairs; no pooling or round pairing."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=REPOSITORY / "benchmarking/data")
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    inventory = discover_pairs(args.data_root.resolve())
    if args.inventory_only:
        print(json.dumps(inventory, indent=2))
        return
    if not inventory["pairs"]:
        raise ValueError("No compatible merged/unmerged pairs found")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    report = OUTPUT_ROOT / "bootstrap-reports" / stamp
    report.mkdir(parents=True)
    derived = args.data_root.resolve() / "bootstrap" / stamp
    derived.mkdir(parents=True)
    rows, links = [], []
    for number, pair in enumerate(inventory["pairs"], 1):
        settings = pair["matching_settings"]
        name = f"bootstrap-{settings['execution_mode']}-sf{settings['scale_factor']}-pair{number:02d}"
        config = {"name": name,
                  "baseline": {"directory": pair["baseline"], "label": "Unmerged"},
                  "comparison": {"directory": pair["comparison"], "label": "Merged"},
                  "metrics": list(METRICS), "queries": None, "plots": ["change_ci"],
                  "bootstrap": {"resamples": 10000, "confidence": .95, "seed": 0},
                  "queries_per_page": 6, "change_queries_per_page": 13,
                  "output_dir": str(OUTPUT_ROOT)}
        config_path = derived / f"{name}.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        output = render_pair(read_config(config_path))
        pair["output_directory"] = str(output)
        pair["configuration_file"] = str(config_path)
        with (output / "bootstrap_summary.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append({"execution_mode": settings["execution_mode"],
                             "scale_factor": settings["scale_factor"],
                             "baseline_directory": pair["baseline"],
                             "comparison_directory": pair["comparison"], **row})
        figures = sorted((output / "change_ci").glob("*.png"))
        for figure in figures:
            relative = "../../" + str(figure.relative_to(OUTPUT_ROOT))
            links.append(f'<li><a href="{html.escape(relative)}">{html.escape(name + ": " + figure.stem)}</a></li>')
    if rows:
        with (derived / "all_confidence_intervals.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    inventory["bootstrap"] = {"method": "independent percentile bootstrap of median ratio",
                              "resamples": 10000, "confidence": .95, "seed": 0}
    inventory["interval_count"] = len(rows)
    (derived / "coverage.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    csv_link = html.escape(os.path.relpath(derived / "all_confidence_intervals.csv", report))
    coverage_link = html.escape(os.path.relpath(derived / "coverage.json", report))
    (report / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Exploratory bootstrap intervals</title>'
        '<h1>Exploratory bootstrap intervals</h1><p>Unmerged baseline → merged comparison; '
        'negative means faster. Independent resampling within each execution; '
        'intervals do not capture between-session variation or drift.</p>'
        f'<p><a href="{csv_link}">All numeric intervals (CSV)</a> · '
        f'<a href="{coverage_link}">Coverage and matching settings</a></p><ul>' + ''.join(links) + '</ul>',
        encoding="utf-8")
    write_index(OUTPUT_ROOT)
    print(f"Bootstrap data: {derived}")
    print(f"Bootstrap report: {report / 'index.html'}")
    print(f"Pairs: {len(inventory['pairs'])}; intervals: {len(rows)}; unmatched: {len(inventory['unmatched_directories'])}")


if __name__ == "__main__":
    main()
