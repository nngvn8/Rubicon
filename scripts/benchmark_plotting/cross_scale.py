"""Configuration, validation and export for comparisons across scale factors."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from data import METRICS, check_comparison, load_experiment, natural_key, values
from index import canonical_json, configuration_metadata, flatten_metadata

ROLES = ("baseline", "comparison")


def read_cross_scale_config(section, parent):
    if not isinstance(section, dict) or set(section) - {"pairs", "metric", "scaling_interval", "color_limits"}:
        raise ValueError("cross_scale must contain only pairs, metric, scaling_interval and color_limits")
    metric = section.get("metric", "total_response_time")
    if not isinstance(metric, str) or metric not in METRICS:
        raise ValueError(f"cross_scale.metric must be one of {list(METRICS)}")
    pairs = section.get("pairs")
    if not isinstance(pairs, list) or len(pairs) < 2:
        raise ValueError("cross_scale.pairs must contain at least two input pairs")
    resolved, seen = [], set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != set(ROLES):
            raise ValueError("Each cross_scale pair must specify baseline and comparison directories")
        item = {}
        for role in ROLES:
            directory = pair[role]
            if not isinstance(directory, str) or not directory.strip():
                raise ValueError(f"cross_scale pair {role} must be a nonempty directory string")
            directory = (parent / directory).resolve()
            if directory in seen:
                raise ValueError(f"Duplicate cross_scale input directory: {directory}")
            seen.add(directory)
            item[role] = directory
        resolved.append(item)
    interval = section.get("scaling_interval")
    if interval is not None:
        if (not isinstance(interval, list) or len(interval) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in interval)
                or interval[0] >= interval[1]):
            raise ValueError("cross_scale.scaling_interval must contain two increasing positive scale factors")
    limits = section.get("color_limits", [-20, 20])
    if (not isinstance(limits, list) or len(limits) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in limits)
            or not limits[0] < 0 < limits[1]):
        raise ValueError("cross_scale.color_limits must contain two finite numbers spanning zero")
    return {"pairs": resolved, "metric": metric, "scaling_interval": interval, "color_limits": limits}


def cross_scale_inputs(config):
    inputs = []
    for pair in config["cross_scale"]["pairs"]:
        entry = {}
        for role in ROLES:
            path = pair[role] / "results.json"
            raw = path.read_bytes()
            entry[role] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
            if role == "baseline":
                document = json.loads(raw)
                if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
                    raise ValueError(f"{path}: expected metadata object")
                entry["scale_factor"] = document["metadata"].get("scale_factor")
        inputs.append(entry)
    return inputs


def require_matching_settings(a, b, context, ignored=()):
    first = {k: v for k, v in configuration_metadata(a).items() if k not in ignored}
    second = {k: v for k, v in configuration_metadata(b).items() if k not in ignored}
    left, right = flatten_metadata(first), flatten_metadata(second)
    different = [key for key in sorted(left.keys() | right.keys())
                 if key not in left or key not in right
                 or canonical_json(left[key]) != canonical_json(right[key])]
    if different:
        raise ValueError(f"{context}: incompatible metadata: {', '.join(sorted(set(different)))}")


def prepare_cross_scale(config):
    """Load every input before rendering; preserve notices rather than invent samples."""
    fingerprints = cross_scale_inputs(config)
    pairs, notices = {}, []
    for directories in config["cross_scale"]["pairs"]:
        experiments = tuple(load_experiment(directories[role], config[role]["label"]) for role in ROLES)
        a, b = experiments
        sf = a.metadata["scale_factor"]
        notices.extend(f"SF {sf}: {notice}" for notice in check_comparison(a, b))
        require_matching_settings(a.metadata, b.metadata, f"SF {sf}, baseline vs comparison",
                                  ignored=("optimization", "variant"))
        if sf in pairs:
            raise ValueError(f"Duplicate cross_scale scale factor: {sf}")
        pairs[sf] = experiments
    pairs = dict(sorted(pairs.items()))
    reference = next(iter(pairs.values()))
    for sf, experiments in pairs.items():
        for role, experiment, original in zip(ROLES, experiments, reference):
            if experiment.queries != original.queries:
                raise ValueError(f"SF {sf}, {role}: query sets differ across scale factors")
            require_matching_settings(original.metadata, experiment.metadata,
                                      f"SF {sf}, {role} across scale factors", ignored=("scale_factor",))
    interval = config["cross_scale"]["scaling_interval"] or list(pairs)[-2:]
    if any(sf not in pairs for sf in interval):
        raise ValueError("cross_scale.scaling_interval must reference scale factors present in the input pairs")
    requested = config.get("queries")
    if requested is not None and set(requested) - reference[0].queries:
        raise ValueError(f"Unknown queries: {sorted(set(requested) - reference[0].queries)}")
    queries = sorted(requested or reference[0].queries, key=natural_key)
    metric = config["cross_scale"]["metric"]
    for sf, experiments in pairs.items():
        for role, experiment in zip(ROLES, experiments):
            failures = experiment.failures[experiment.failures["query"].isin(queries)]
            if len(failures):
                notices.append(f"SF {sf}, {role}: {len(failures)} failed query-rounds")
            for query in queries:
                observed = values(experiment, query, metric).dropna()
                expected = experiment.metadata["measured_rounds"]
                if len(observed) != expected:
                    notices.append(f"SF {sf}, {role}, {query}, {metric}: {len(observed)}/{expected} observations")
                if (observed == 0).any():
                    notices.append(f"SF {sf}, {role}, {query}, {metric}: zero observations; ratios require a positive baseline median")
    # Catch writes between fingerprinting and loading as well as during export.
    if fingerprints != cross_scale_inputs(config):
        raise ValueError("Cross-scale inputs changed while loading")
    return pairs, queries, list(interval), notices, fingerprints


def cross_scale_rendering(config, inputs, queries, interval, *, environment=None, code_hashes=None):
    from plot_benchmarks import RENDERING_SOURCES, rendering_environment
    if code_hashes is None:
        code_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                       for name in RENDERING_SOURCES}
    payload = {"schema_version": 2, "kind": "cross_scale",
               "inputs": [{"scale_factor": pair["scale_factor"], **{role: pair[role]["sha256"] for role in ROLES}}
                          for pair in sorted(inputs, key=lambda item: item["scale_factor"])],
               "queries": list(queries), "metric": config["cross_scale"]["metric"],
               "labels": {role: config[role]["label"] for role in ROLES},
               "scaling_interval": interval, "color_limits": config["cross_scale"].get("color_limits", [-20, 20]),
               "code": code_hashes,
               "environment": rendering_environment() if environment is None else environment}
    return {"sha256": hashlib.sha256(canonical_json(payload).encode()).hexdigest(), "payload": payload}


def write_cross_scale_manifest(output, final, config, prepared, rendering):
    pairs, queries, interval, notices, inputs = prepared
    if inputs != cross_scale_inputs(config):
        raise ValueError("Benchmark inputs changed during plotting; cross-scale batch was not published")
    if rendering != cross_scale_rendering(config, inputs, queries, interval):
        raise ValueError("Rendering code or environment changed during plotting; cross-scale batch was not published")
    entries = []
    for hashes in sorted(inputs, key=lambda item: item["scale_factor"]):
        sf = hashes["scale_factor"]
        entries.append({"scale_factor": sf, **{role: {**hashes[role], "metadata": pairs[sf][i].metadata}
                                               for i, role in enumerate(ROLES)}})
    # Common metadata supports the existing index; full per-input metadata remains above.
    metadata = {}
    for i, role in enumerate(ROLES):
        metadata[role] = configuration_metadata(next(iter(pairs.values()))[i].metadata)
        metadata[role].update(scale_factor=list(pairs), comparison_kind="cross_scale")
    resolved_config = {**config, "plots": ["cross_scale"], "metrics": [config["cross_scale"]["metric"]],
                       "cross_scale": {**config["cross_scale"], "scaling_interval": interval}}
    manifest = {"kind": "cross_scale", "batch_id": final.name,
                "generated_at": datetime.now(timezone.utc).isoformat(), "config": resolved_config,
                "inputs": {role: {"metadata": metadata[role]} for role in ROLES},
                "scale_pairs": entries, "queries": queries, "notices": notices,
                "statistics": {"heatmap": "100 * (median(comparison) / median(baseline) - 1)",
                               "scaling": "median(higher scale) / median(lower scale)"},
                "figures": ["cross_scale.png"], "rendering": rendering}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")


def render_cross_scale(config, prepared):
    from plot_benchmarks import output_batch
    from plots import plot_cross_scale, configuration_caption, add_configuration_caption
    import matplotlib.pyplot as plt
    pairs, queries, interval, notices, inputs = prepared
    rendering = cross_scale_rendering(config, inputs, queries, interval)
    description = f"{config['name']}_cross-scale" if config.get("name") else "cross-scale"
    with output_batch(config["output_dir"], description=description) as (output, final):
        figure = plot_cross_scale(pairs, queries, config["cross_scale"]["metric"], interval,
                                  config["cross_scale"].get("color_limits", [-20, 20]))
        try:
            caption = [f"Batch: {final.name} | Cross-scale comparison; full inputs and settings: manifest.json"]
            for sf, experiments in pairs.items():
                hashes = next(item for item in inputs if item["scale_factor"] == sf)
                local = {role: {"directory": Path(hashes[role]["path"]).parent} for role in ROLES}
                caption.append(f"Scale factor {sf}")
                caption.extend(configuration_caption(local, experiments, final.name)[1:])
            add_configuration_caption(figure, caption)
            figure.savefig(output / "cross_scale.png", dpi=160, bbox_inches="tight")
        finally:
            plt.close(figure)
        write_cross_scale_manifest(output, final, config, prepared, rendering)
    return final
