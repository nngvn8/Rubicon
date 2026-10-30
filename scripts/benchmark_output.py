"""Compact comparison names and isolated, reproducible plotting batches."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import tempfile

# Keep aliases explicit: unknown settings retain their full key and value.
MATERIALIZATION_ALIASES = {
    "materialize_into_join": "join",
    "materialize_into_group": "group",
    "materialize_into_operator": "operator",
}


def validate_name(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.=-]*", value) or "__vs__" in value:
        raise ValueError(f"{field} must be a single filename component using letters, numbers, _, ., = or -")
    return value


def compact_variant(metadata, directory):
    variant = metadata.get("variant")
    if not isinstance(variant, dict) or not variant:
        # The experiment directory's parent normally names its variant.
        fallback = re.sub(r"[^A-Za-z0-9_.=-]+", "-", directory.parent.name).strip(".-")
        return fallback or "unspecified"
    enabled = []
    extra = []
    for key, value in sorted(variant.items()):
        if key in MATERIALIZATION_ALIASES and type(value) is bool:
            if value:
                enabled.append(MATERIALIZATION_ALIASES[key])
        else:
            # Percent encoding prevents different punctuation from collapsing
            # to the same compact name, and encodes path separators safely.
            from urllib.parse import quote
            token = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
            extra.append(f"{quote(key, safe='')}={quote(token, safe='')}")
    # Give the common join+group combination its natural reading order.
    enabled.sort(key=lambda name: (name != "join", name != "group", name))
    base = "mat-" + "-".join(enabled) if enabled else "baseline"
    return "_".join([base, *extra])


def comparison_name(config, experiments):
    ids = [config[role].get("id") or compact_variant(experiment.metadata, config[role]["directory"])
           for role, experiment in zip(("baseline", "comparison"), experiments)]
    return config.get("name") or f"{ids[0]}__vs__{ids[1]}"


def comparison_parent(config, experiments):
    return config["output_dir"] / "batches"


def input_fingerprints(config):
    return {role: {"path": str(config[role]["directory"] / "results.json"),
                   "sha256": hashlib.sha256((config[role]["directory"] / "results.json").read_bytes()).hexdigest()}
            for role in ("baseline", "comparison")}


RENDERING_SOURCES = ("benchmark_data.py", "benchmark_figures.py", "benchmark_output.py", "plot_benchmarks.py")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


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
        "notices": notices,
        "figures": sorted(str(path.relative_to(output)) for path in output.rglob("*.png")),
    }
    if rendering is not None:
        if rendering_fingerprint(config, fingerprints, queries) != rendering:
            raise ValueError("Rendering code or environment changed during plotting; batch was not published.")
        manifest["rendering"] = rendering
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def configuration_caption(config, experiments, batch_id):
    """Use recorded metadata only; paths and verbose provenance stay in the manifest."""
    lines = [f"Batch: {batch_id} | Configuration from input metadata; full details: manifest.json"]
    provenance = {"created_at", "query_order", "config_file", "experiment"}
    for role, experiment in zip(("baseline", "comparison"), experiments):
        metadata = experiment.metadata
        settings = {key: value for key, value in metadata.items() if key not in provenance}
        # Preserve structured experiment settings while keeping prose notes in
        # the manifest instead of filling the figure with paragraphs.
        if "experiment" in metadata:
            experiment_settings = metadata["experiment"]
            if isinstance(experiment_settings, dict):
                experiment_settings = {k: v for k, v in experiment_settings.items() if k not in ("notes", "reason")}
            if experiment_settings:
                settings["experiment"] = experiment_settings
        encoded = "; ".join(f"{key}={json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))}"
                            for key, value in sorted(settings.items()))
        lines.append(f"{role.capitalize()} ({experiment.label}): {encoded}")
        lines.append(f"Input: {config[role]['directory'].name}")
    return lines


def add_configuration_caption(figure, lines):
    """Extend the figure below its existing layout without covering plot content."""
    import textwrap

    width, height = figure.get_size_inches()
    wrapped = [part for line in lines for part in textwrap.wrap(line, width=max(40, int(width * 17)), break_long_words=True)]
    footer_height = .25 + .13 * len(wrapped)
    total_height = height + footer_height
    factor, offset = height / total_height, footer_height / total_height
    # Figure-level legends need their anchors captured before the resize.
    legend_boxes = [(legend, legend.get_bbox_to_anchor().transformed(figure.transFigure.inverted()))
                    for legend in figure.legends]
    figure.set_size_inches(width, total_height)
    for axis in figure.axes:
        x, y, w, h = axis.get_position().bounds
        axis.set_position((x, offset + factor * y, w, factor * h))
    for text in figure.texts:
        x, y = text.get_position()
        text.set_position((x, offset + factor * y))
    for legend, box in legend_boxes:
        legend.set_bbox_to_anchor((box.x0, offset + factor * box.y0, box.width, factor * box.height), transform=figure.transFigure)
    figure.text(.015, .08 / total_height, "\n".join(wrapped), ha="left", va="bottom", fontsize=7, family="monospace", linespacing=1.25)
