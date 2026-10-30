#!/usr/bin/env python3
"""Compare two benchmark executions using a JSON configuration file.

Paths in the configuration are relative to the configuration file.
See benchmark_plot_config.json and README_benchmark_plots.md for an example.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmark_data import METRICS, check_comparison, load_experiment, natural_key, values
from benchmark_output import comparison_name, comparison_parent, input_fingerprints, output_batch, validate_name, write_manifest, configuration_caption, add_configuration_caption, rendering_fingerprint


PLOTS = ("change", "distribution", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance")


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    allowed = {"baseline", "comparison", "metrics", "queries", "plots", "output_dir", "queries_per_page", "change_queries_per_page", "name"}
    if set(config) - allowed:
        raise ValueError(f"Unknown configuration fields: {sorted(set(config) - allowed)}")
    for role in ("baseline", "comparison"):
        item = config.get(role)
        if not isinstance(item, dict) or not {"directory", "label"} <= set(item) or set(item) - {"directory", "label", "id"} or not all(isinstance(item[k], str) and item[k].strip() for k in item):
            raise ValueError(f"{role} must specify nonempty directory and label strings")
        if "id" in item:
            validate_name(item["id"], f"{role}.id")
        item["directory"] = (path.parent / item["directory"]).resolve()
    if config["baseline"]["label"] == config["comparison"]["label"]:
        raise ValueError("Experiment labels must differ")
    if config["baseline"]["directory"] == config["comparison"]["directory"]:
        raise ValueError("Select two different experiment directories")
    for key, default, choices in (("metrics", ["total_response_time"], METRICS), ("plots", ["change", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance"], PLOTS)):
        items = config.setdefault(key, default)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or item not in choices for item in items) or len(items) != len(set(items)):
            raise ValueError(f"{key} must be a nonempty list of unique choices from {list(choices)}")
    queries = config.get("queries")
    if queries is not None and (not isinstance(queries, list) or not queries or any(not isinstance(q, str) for q in queries) or len(queries) != len(set(queries))):
        raise ValueError("queries must be null or a nonempty list of unique plan filenames")
    page_size = config.setdefault("queries_per_page", 6)
    if type(page_size) is not int or page_size < 1:
        raise ValueError("queries_per_page must be a positive integer")
    change_size = config.setdefault("change_queries_per_page", 13)
    if type(change_size) is not int or change_size < 1:
        raise ValueError("change_queries_per_page must be a positive integer")
    if "name" in config:
        validate_name(config["name"], "name")
    output = config.get("output_dir", "../generated/benchmark-comparisons")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output_dir must be a nonempty string")
    config["output_dir"] = (path.parent / output).resolve()
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("benchmark_plot_config.json"))
    args = parser.parse_args()
    try:
        config = read_config(args.config.resolve())
        fingerprints = input_fingerprints(config)
        experiments = tuple(load_experiment(config[role]["directory"], config[role]["label"]) for role in ("baseline", "comparison"))
        notices = check_comparison(*experiments)
        for message in notices:
            print(f"Notice: {message}", file=sys.stderr)
        requested = config.get("queries")
        if requested is not None and set(requested) - experiments[0].queries:
            raise ValueError(f"Unknown queries: {sorted(set(requested) - experiments[0].queries)}")
        queries = sorted(requested or experiments[0].queries, key=natural_key)
        for experiment in experiments:
            failures = experiment.failures[experiment.failures["query"].isin(queries)]
            print(f"{experiment.label}: {len(queries)} queries; {len(failures)} failed query-rounds")
            for query in queries:
                for metric in config["metrics"]:
                    count = int(values(experiment, query, metric).count())
                    expected = experiment.metadata["measured_rounds"]
                    if count != expected:
                        print(f"Notice: {experiment.label}, {query}, {metric}: {count}/{expected} observations", file=sys.stderr)
        from benchmark_figures import plot_change, plot_panels, plot_metric_comparison, plot_metric_relationships, plot_duration_exceedance
        import matplotlib.pyplot as plt
        rendering = rendering_fingerprint(config, fingerprints, queries)
        parent = comparison_parent(config, experiments)
        with output_batch(parent, description=comparison_name(config, experiments)) as (output, final):
            caption = configuration_caption(config, experiments, final.name)
            for kind, renderer in (("metric_comparison", plot_metric_comparison),
                                    ("metric_relationships", plot_metric_relationships),
                                    ("duration_exceedance", plot_duration_exceedance)):
                if kind not in config["plots"]:
                    continue
                figure = renderer(experiments, queries, config["metrics"])
                path = output / f"{kind}.png"
                try:
                    add_configuration_caption(figure, caption)
                    figure.savefig(path, dpi=160, bbox_inches="tight")
                finally:
                    plt.close(figure)
                print(f"Rendered {path.relative_to(output)}")
            for metric in config["metrics"]:
                for kind in config["plots"]:
                    if kind in ("metric_comparison", "metric_relationships", "duration_exceedance"):
                        continue
                    page_size = config["change_queries_per_page"] if kind == "change" else config["queries_per_page"]
                    pages = [queries[start:start + page_size] for start in range(0, len(queries), page_size)]
                    for page, selected in enumerate(pages, 1):
                        if kind == "change":
                            figure = plot_change(experiments, selected, metric)
                        else:
                            figure = plot_panels(experiments, selected, metric, kind)
                        path = output / kind / f"{metric}_{page:02d}.png"
                        path.parent.mkdir(exist_ok=True)
                        try:
                            add_configuration_caption(figure, caption)
                            figure.savefig(path, dpi=160, bbox_inches="tight")
                        finally:
                            plt.close(figure)
                        print(f"Rendered {path.relative_to(output)}")
            write_manifest(output, config, experiments, fingerprints, queries, notices, final.name, rendering)
        print(f"Completed batch: {final}")
        from benchmark_index import write_index
        print(f"Updated index: {write_index(config['output_dir'])}")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
