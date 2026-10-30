"""Load benchmark observations and calculate descriptive comparisons."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

METRICS = {
    "total_response_time": {"label": "Response time", "unit": "s"},
    "plan_duration": {"label": "Plan duration", "unit": "s"},
    "operator_work": {"label": "Operator work", "unit": "s"},
}


@dataclass
class Experiment:
    label: str
    metadata: dict
    queries: set[str]
    observations: pd.DataFrame
    failures: pd.DataFrame


def natural_key(name: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def load_experiment(directory: Path, label: str) -> Experiment:
    path = directory / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict) or not isinstance(data.get("queries"), dict) or not data["queries"]:
        raise ValueError(f"{path}: expected metadata and nonempty queries objects")
    metadata = data["metadata"]
    for field in ("workers_per_cu", "scale_factor", "measured_rounds"):
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{path}: invalid metadata.{field}")
    rounds = metadata["measured_rounds"]
    if not isinstance(rounds, int):
        raise ValueError(f"{path}: measured_rounds must be an integer")
    rows, failures = [], []
    for query, result in data["queries"].items():
        if not isinstance(result, dict) or not isinstance(result.get("samples"), list) or not isinstance(result.get("failures", []), list):
            raise ValueError(f"{path}: {query}: expected samples and failures lists")
        seen = set()
        for kind, records in (("sample", result["samples"]), ("failure", result.get("failures", []))):
            for record in records:
                round_number = record.get("round") if isinstance(record, dict) else None
                if type(round_number) is not int or not 1 <= round_number <= rounds or round_number in seen:
                    raise ValueError(f"{path}: {query}: invalid or duplicate round {round_number}")
                seen.add(round_number)
                if kind == "failure":
                    failures.append({"query": query, "round": round_number, "error": record.get("error", "unknown")})
                    continue
                for metric in METRICS:
                    value = record.get(metric)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                        raise ValueError(f"{path}: {query}, round {round_number}: invalid {metric}")
                    rows.append({"query": query, "round": round_number, "metric": metric, "value_seconds": value})
    return Experiment(label, metadata, set(data["queries"]), pd.DataFrame(rows, columns=["query", "round", "metric", "value_seconds"]), pd.DataFrame(failures, columns=["query", "round", "error"]))


def check_comparison(baseline: Experiment, comparison: Experiment) -> list[str]:
    if baseline.queries != comparison.queries:
        raise ValueError("Experiment query sets differ")
    for field in ("workers_per_cu", "scale_factor"):
        if baseline.metadata[field] != comparison.metadata[field]:
            raise ValueError(f"Incompatible {field}: {baseline.metadata[field]} vs {comparison.metadata[field]}")
    return [f"Metadata differs: {field}: {baseline.metadata.get(field)!r} vs {comparison.metadata.get(field)!r}" for field in ("host", "warmup_rounds", "query_order", "variant", "plan_source", "cu_restarted_between_runs") if baseline.metadata.get(field) != comparison.metadata.get(field)]


def values(experiment: Experiment, query: str, metric: str) -> pd.Series:
    data = experiment.observations
    selected = data[(data["query"] == query) & (data["metric"] == metric)]
    return selected.set_index("round")["value_seconds"].sort_index().astype(float)


def summarize(baseline: Experiment, comparison: Experiment, queries: list[str], metric: str) -> pd.DataFrame:
    rows = []
    for query in queries:
        a, b = values(baseline, query, metric).dropna(), values(comparison, query, metric).dropna()
        am, bm = a.median(), b.median()
        rows.append({"query": query, "baseline": am, "comparison": bm, "baseline_n": len(a), "comparison_n": len(b), "difference": bm - am, "percent": 100 * (bm / am - 1) if len(a) and len(b) and am > 0 else float("nan")})
    return pd.DataFrame(rows).set_index("query")


def summarize_changes(baseline, comparison, queries, metric):
    """Describe all unpaired timing ratios; combinations are not independent samples."""
    rows = []
    for query in queries:
        a = values(baseline, query, metric).dropna()
        b = values(comparison, query, metric).dropna()
        row = {"query": query, "baseline_n": len(a), "comparison_n": len(b)}
        # A zero reference makes relative improvements undefined. Do not silently
        # remove it and change the empirical baseline distribution.
        if len(a) and len(b) and (a > 0).all():
            pairs = pd.DataFrame([
                (100 * (bv / av - 1), bv - av)
                for av in a for bv in b
            ], columns=["percent", "delta"]).sort_values("percent", kind="stable")
            changes = pairs["percent"]
            row.update(dict(zip(
                ("p05", "q1", "median", "q3", "p95"),
                changes.quantile([.05, .25, .5, .75, .95]),
            )))
            # Interpolate the corresponding absolute deltas at exactly the
            # same ranked pairs used for each percentage whisker endpoint.
            for name, quantile in (("p05", .05), ("p95", .95)):
                rank = (len(pairs) - 1) * quantile
                lower, upper = math.floor(rank), math.ceil(rank)
                weight = rank - lower
                row[f"{name}_delta"] = ((1 - weight) * pairs.iloc[lower]["delta"]
                                        + weight * pairs.iloc[upper]["delta"])
        else:
            row.update(dict.fromkeys(("p05", "q1", "median", "q3", "p95", "p05_delta", "p95_delta"), float("nan")))
        rows.append(row)
    return pd.DataFrame(rows).set_index("query")


def duration_exceedance_counts(experiment, queries):
    """Count strict plan-duration > work comparisons within the same round."""
    rows = []
    for query in queries:
        paired = pd.concat([
            values(experiment, query, "plan_duration").rename("duration"),
            values(experiment, query, "operator_work").rename("work"),
        ], axis=1).dropna()
        count = int((paired["duration"] > paired["work"]).sum())
        total = len(paired)
        rows.append({"query": query, "count": count, "total": total,
                     "percent": 100 * count / total if total else float("nan")})
    return pd.DataFrame(rows).set_index("query")
