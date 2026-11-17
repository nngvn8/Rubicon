#!/usr/bin/env python3
"""Compare two benchmark executions using a JSON configuration file.

Paths in the configuration are relative to the configuration file.
See config.json and README.md for an example.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import hashlib
import stat
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
import re

from data import METRICS, check_comparison, load_experiment, natural_key, values
from index import canonical_json, compact_variant
from plots import configuration_caption, add_configuration_caption


OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "benchmarking/plots/runtime"
RENDERING_SOURCES = ("data.py", "plots.py", "plot_benchmarks.py", "index.py", "cross_scale.py", "bootstrap.py")

def validate_name(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.=-]*", value) or "__vs__" in value:
        raise ValueError(f"{field} must be a single filename component using letters, numbers, _, ., = or -")
    return value



def comparison_name(config, experiments):
    ids = [config[role].get("id") or compact_variant(experiment.metadata, config[role]["directory"])
           for role, experiment in zip(("baseline", "comparison"), experiments)]
    return config.get("name") or f"{ids[0]}__vs__{ids[1]}"



def comparison_parent(config, experiments):
    return config["output_dir"]



def input_fingerprints(config):
    return {role: {"path": str(config[role]["directory"] / "results.json"),
                   "sha256": hashlib.sha256((config[role]["directory"] / "results.json").read_bytes()).hexdigest()}
            for role in ("baseline", "comparison")}



def rendering_environment():
    import platform
    import matplotlib
    import numpy
    import pandas
    from matplotlib import ft2font

    return {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
            "numpy": numpy.__version__, "pandas": pandas.__version__,
            "freetype": ft2font.__freetype_version__, "backend": str(matplotlib.get_backend())}



def rendering_fingerprint(config, inputs, queries, *, environment=None, code_hashes=None):
    """Hash rendering-relevant inputs; paths, generation IDs and index code are excluded."""
    if code_hashes is None:
        code_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                       for name in RENDERING_SOURCES}
    payload = {
        "schema_version": 1,
        "inputs": {role: inputs[role]["sha256"] for role in ("baseline", "comparison")},
        "queries": list(queries),
        "metrics": list(config["metrics"]),
        "plots": sorted(config["plots"]),
        "labels": {role: config[role]["label"] for role in ("baseline", "comparison")},
        "pagination": {key: config[key] for key in ("queries_per_page", "change_queries_per_page")},
        "bootstrap": config.get("bootstrap", {}),
        "code": code_hashes,
        "environment": rendering_environment() if environment is None else environment,
    }
    return {"sha256": hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(), "payload": payload}



@contextmanager
def output_batch(parent, timestamp=None, description=None):
    """Publish a complete batch atomically; reserve names across concurrent runs."""
    parent.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    if description:
        stamp = f"{stamp}_{description}"
    suffix = 0
    while True:
        name = stamp if not suffix else f"{stamp}_{suffix:02d}"
        final = parent / name
        reservation = parent / f".{name}.reserved"
        try:
            reservation.mkdir()
        except FileExistsError:
            suffix += 1
            continue
        if final.exists():
            reservation.rmdir()
            suffix += 1
            continue
        break
    try:
        with tempfile.TemporaryDirectory(prefix=".plotting-", dir=parent) as temporary:
            staging = Path(temporary)
            yield staging, final
            # TemporaryDirectory starts at 0700; published output should use
            # the same access permissions as its surrounding output folder.
            staging.chmod(stat.S_IMODE(parent.stat().st_mode) & 0o777)
            staging.rename(final)
    finally:
        reservation.rmdir()



def write_manifest(output, config, experiments, fingerprints, queries, notices, batch_id=None, rendering=None):
    if input_fingerprints(config) != fingerprints:
        raise ValueError("Benchmark inputs changed during plotting; batch was not published. Rerun with stable inputs.")
    manifest = {
        "batch_id": batch_id or output.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "inputs": {role: {**fingerprints[role], "metadata": experiment.metadata}
                   for role, experiment in zip(("baseline", "comparison"), experiments)},
        "queries": queries,
        "statistics": {
            "percentage_change": "100 * (median(comparison) / median(baseline) - 1)",
            "change_intervals": "comparison timing quantiles normalized against baseline median",
            "bootstrap_intervals": "independent percentile bootstrap of 100 * (median(comparison) / median(baseline) - 1); assumes independent observations; no between-session uncertainty",
        },
        "notices": notices,
        "figures": sorted(str(path.relative_to(output)) for path in output.rglob("*.png")),
    }
    if "change_ci" in config.get("plots", []):
        from bootstrap import DEFAULTS
        manifest["statistics"]["bootstrap"] = {**DEFAULTS, **config.get("bootstrap", {}),
                                                   "method": "percentile", "resampling": "independent samples"}
        manifest["tables"] = ["bootstrap_summary.csv"]
    if rendering is not None:
        if rendering_fingerprint(config, fingerprints, queries) != rendering:
            raise ValueError("Rendering code or environment changed during plotting; batch was not published.")
        manifest["rendering"] = rendering
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


PLOTS = ("change_ci", "change", "distribution", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance", "cross_scale")


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    allowed = {"baseline", "comparison", "metrics", "queries", "plots", "output_dir", "queries_per_page", "change_queries_per_page", "name", "cross_scale", "bootstrap"}
    if set(config) - allowed:
        raise ValueError(f"Unknown configuration fields: {sorted(set(config) - allowed)}")
    plots = config.get("plots", ["change", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance"])
    cross_only = plots == ["cross_scale"]
    for role in ("baseline", "comparison"):
        item = config.get(role)
        if not isinstance(item, dict) or not ({"label"} if cross_only else {"directory", "label"}) <= set(item) or set(item) - {"directory", "label", "id"} or not all(isinstance(item[k], str) and item[k].strip() for k in item):
            raise ValueError(f"{role} must specify nonempty directory and label strings")
        if "id" in item:
            validate_name(item["id"], f"{role}.id")
        if "directory" in item:
            item["directory"] = (path.parent / item["directory"]).resolve()
    if config["baseline"]["label"] == config["comparison"]["label"]:
        raise ValueError("Experiment labels must differ")
    if not cross_only and config["baseline"]["directory"] == config["comparison"]["directory"]:
        raise ValueError("Select two different experiment directories")
    for key, default, choices in (("metrics", ["total_response_time"], METRICS), ("plots", ["change", "rounds", "metric_comparison", "metric_relationships", "duration_exceedance"], PLOTS)):
        items = config.setdefault(key, default)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or item not in choices for item in items) or len(items) != len(set(items)):
            raise ValueError(f"{key} must be a nonempty list of unique choices from {list(choices)}")
    from bootstrap import DEFAULTS
    bootstrap = config.setdefault("bootstrap", {})
    if not isinstance(bootstrap, dict) or set(bootstrap) - set(DEFAULTS):
        raise ValueError("bootstrap accepts only resamples, confidence, seed")
    config["bootstrap"] = {**DEFAULTS, **bootstrap}
    # Reuse the statistical function's option validation, without observations.
    from bootstrap import bootstrap_median_change
    bootstrap_median_change([], [], **config["bootstrap"])
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
    output = config.get("output_dir", str(OUTPUT_ROOT))
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output_dir must be a nonempty string")
    if (path.parent / output).resolve() != OUTPUT_ROOT:
        raise ValueError(f"output_dir must be {OUTPUT_ROOT}")
    config["output_dir"] = OUTPUT_ROOT
    if "cross_scale" in config:
        from cross_scale import read_cross_scale_config
        config["cross_scale"] = read_cross_scale_config(config["cross_scale"], path.parent)
    if "cross_scale" in config["plots"] and "cross_scale" not in config:
        raise ValueError("The cross_scale plot requires a cross_scale configuration section")
    return config


def render_pair(config):
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
    from plots import plot_change_ci, plot_change, plot_panels, plot_metric_comparison, plot_metric_relationships, plot_duration_exceedance
    import matplotlib.pyplot as plt
    rendering = rendering_fingerprint(config, fingerprints, queries)
    parent = comparison_parent(config, experiments)
    with output_batch(parent, description=comparison_name(config, experiments)) as (output, final):
        caption = configuration_caption(config, experiments, final.name)
        bootstrap_tables = {}
        if "change_ci" in config["plots"]:
            from bootstrap import summarize_bootstrap
            import pandas as pd
            for metric in config["metrics"]:
                bootstrap_tables[metric] = summarize_bootstrap(*experiments, queries, metric, **config.get("bootstrap", {}))
            pd.concat(bootstrap_tables, names=["metric", "query"]).reset_index().to_csv(output / "bootstrap_summary.csv", index=False)
            notices.append("Bootstrap CIs assume independent observations within each input; they do not include between-session variation or correct execution-order bias.")
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
                page_size = config["change_queries_per_page"] if kind in ("change", "change_ci") else config["queries_per_page"]
                pages = [queries[start:start + page_size] for start in range(0, len(queries), page_size)]
                for page, selected in enumerate(pages, 1):
                    if kind == "change_ci":
                        figure = plot_change_ci(experiments, selected, metric,
                                                summary=bootstrap_tables[metric].loc[selected],
                                                **config.get("bootstrap", {}))
                    elif kind == "change":
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
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    args = parser.parse_args()
    try:
        config = read_config(args.config.resolve())
        prepared = None
        if "cross_scale" in config["plots"]:
            from cross_scale import prepare_cross_scale, render_cross_scale
            prepared = prepare_cross_scale(config)
            for notice in prepared[3]:
                print(f"Notice: {notice}", file=sys.stderr)
        ordinary = [kind for kind in config["plots"] if kind != "cross_scale"]
        if ordinary:
            render_pair({**config, "plots": ordinary})
        if prepared is not None:
            print(f"Completed cross-scale batch: {render_cross_scale(config, prepared)}")
        from index import write_index
        print(f"Updated index: {write_index(config['output_dir'])}")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
