#!/usr/bin/env python3
"""Build a standalone HTML batch index from manifests, optionally flattening old batches."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import warnings

from benchmark_output import canonical_json, compact_variant


def flatten_metadata(metadata, prefix=""):
    """Index both structured settings and their leaves, without interpreting values."""
    fields = {}
    for key, value in metadata.items():
        name = f"{prefix}.{key}" if prefix else key
        fields[name] = value
        if isinstance(value, dict):
            fields.update(flatten_metadata(value, name))
    return fields


GROUP_IGNORED_FIELDS = {"created_at", "config_file"}
GROUP_IGNORED_EXPERIMENT_FIELDS = {"notes", "reason"}


def configuration_metadata(metadata):
    settings = {key: value for key, value in metadata.items() if key not in GROUP_IGNORED_FIELDS}
    if isinstance(settings.get("experiment"), dict):
        experiment = {key: value for key, value in settings["experiment"].items()
                      if key not in GROUP_IGNORED_EXPERIMENT_FIELDS}
        if experiment:
            settings["experiment"] = experiment
        else:
            settings.pop("experiment")
    return settings


def verified_rendering(manifest):
    rendering = manifest.get("rendering")
    if not isinstance(rendering, dict) or not isinstance(rendering.get("payload"), dict):
        return None
    payload = rendering["payload"]
    if payload.get("schema_version") != 1:
        return None
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    if digest != rendering.get("sha256"):
        return None
    if payload.get("inputs") != {role: manifest["inputs"][role].get("sha256") for role in ("baseline", "comparison")}:
        return None
    config = manifest["config"]
    expected = {
        "queries": manifest.get("queries", []), "metrics": config.get("metrics"),
        "plots": sorted(config.get("plots", [])),
        "labels": {role: config[role]["label"] for role in ("baseline", "comparison")},
        "pagination": {key: config.get(key) for key in ("queries_per_page", "change_queries_per_page")},
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        return None
    return rendering


def rendering_difference(a, b):
    if not a or not b:
        return "Fingerprint unavailable for one or both batches"
    names = {"inputs": "Input contents", "queries": "Query selection/order", "metrics": "Metrics/order",
             "plots": "Plot types", "labels": "Labels", "pagination": "Pagination",
             "code": "Plotting code", "environment": "Rendering environment", "schema_version": "Fingerprint schema"}
    changed = [label for key, label in names.items() if a["payload"].get(key) != b["payload"].get(key)]
    return "; ".join(changed) or "Same rendering fingerprint"


def annotate_records(records):
    """Records are newest first, so the first fingerprint occurrence is retained."""
    fingerprints = {}
    source_pairs = {}
    by_uid = {record["uid"]: record for record in records}
    for record in records:
        rendering = record["rendering"]
        record["redundant_of"] = None
        record["equivalent_ids"] = []
        record["related"] = []
        if rendering:
            fingerprints.setdefault(rendering["sha256"], []).append(record)
        directories = tuple(record["source_directories"][role] for role in ("baseline", "comparison"))
        if all(directories):
            source_pairs.setdefault(directories, []).append(record)
    for matching in fingerprints.values():
        latest = matching[0]
        for record in matching:
            record["equivalent_ids"] = [other["uid"] for other in matching if other is not record]
            if record is not latest:
                record["redundant_of"] = latest["uid"]
    for matching in source_pairs.values():
        for record in matching:
            peers = {other["uid"]: other for other in matching if other is not record}
            # Identical contents in different directories can still be redundant.
            for uid in record["equivalent_ids"]:
                peers.setdefault(uid, by_uid[uid])
            for other in peers.values():
                record["related"].append({"uid": other["uid"], "generated": other["generated"],
                    "id": other["id"], "reason": rendering_difference(record["rendering"], other["rendering"])})
    return records


def batch_records(root):
    records = []
    for path in sorted(root.rglob("manifest.json")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            inputs = manifest["inputs"]
            metadata = {role: inputs[role]["metadata"] for role in ("baseline", "comparison")}
            config = manifest["config"]
            settings = {role: configuration_metadata(value) for role, value in metadata.items()}
            group_id = hashlib.sha256(canonical_json(settings).encode("utf-8")).hexdigest()
            source_directories = {}
            for role in metadata:
                directory = config[role].get("directory")
                if directory is None and inputs[role].get("path"):
                    directory = str(Path(inputs[role]["path"]).parent)
                source_directories[role] = str(Path(directory).resolve()) if directory else None
            record = {
                "uid": hashlib.sha256(str(path.parent.resolve()).encode("utf-8")).hexdigest()[:20],
                "group_id": group_id,
                "source_directories": source_directories,
                "rendering": verified_rendering(manifest),
                "id": manifest.get("batch_id", path.parent.name),
                "generated": manifest["generated_at"],
                "directory": str(path.parent.resolve()),
                "manifest": path.relative_to(root).as_posix(),
                "labels": {role: config[role]["label"] for role in metadata},
                "metadata": metadata,
                "fields": {role: flatten_metadata(value) for role, value in metadata.items()},
                "figures": len(manifest["figures"]),
                "queries": manifest.get("queries", []),
                "notices": manifest.get("notices", []),
            }
            records.append(record)
        except (OSError, ValueError, KeyError, TypeError) as error:
            warnings.warn(f"Skipping invalid manifest {path}: {error}")
    records.sort(key=lambda record: (datetime.fromisoformat(record["generated"]).timestamp(), record["directory"]), reverse=True)
    return annotate_records(records)


def migrate_batches(root):
    """Move completed legacy batches only; preserve manifests, images and batch IDs."""
    target_root = root / "batches"
    target_root.mkdir(parents=True, exist_ok=True)
    moved = []
    for record in batch_records(root):
        source = Path(record["directory"])
        if source.parent == target_root.resolve():
            continue
        ids = [compact_variant(record["metadata"][role], Path(source)) for role in ("baseline", "comparison")]
        stem = f"{source.name}_{ids[0]}__vs__{ids[1]}"
        target = target_root / stem
        suffix = 0
        while target.exists():
            suffix += 1
            target = target_root / f"{stem}_{suffix:02d}"
        source.rename(target)
        moved.append(target)
        # Remove only empty old hierarchy directories; never remove their data.
        ancestor = source.parent
        while ancestor != root and ancestor.is_relative_to(root):
            try:
                ancestor.rmdir()
            except OSError:
                break
            ancestor = ancestor.parent
    return moved


def write_index(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    records = batch_records(root)
    template = Path(__file__).with_name("benchmark_index.html").read_text(encoding="utf-8")
    # JSON is inert script data, but closing script tags must still be escaped.
    payload = json.dumps(records, ensure_ascii=True, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    document = template.replace("__BATCH_DATA__", payload)
    # Atomic replacement keeps the previous usable index if writing fails.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=".index-", suffix=".html", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(document)
    try:
        temporary.chmod(0o644)
        temporary.replace(root / "index.html")
    finally:
        temporary.unlink(missing_ok=True)
    return root / "index.html"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "generated/benchmark-comparisons")
    parser.add_argument("--migrate", action="store_true", help="flatten completed legacy batches before building the index")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.migrate:
        for path in migrate_batches(root):
            print(f"Moved batch: {path}")
    print(f"Index: {write_index(root)}")


if __name__ == "__main__":
    main()
