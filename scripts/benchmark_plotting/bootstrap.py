"""Simple, exploratory percentile-bootstrap intervals for changes in medians.

Read ``bootstrap_median_change`` from top to bottom for the statistical recipe.
This deliberately assumes independent observations within each input directory.
It does not estimate variation between separate benchmark sessions.
"""
from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd

from data import values


DEFAULTS = {"resamples": 10000, "confidence": .95, "seed": 0}


def bootstrap_median_change(baseline, comparison, *, resamples=10000, confidence=.95, seed=0):
    """Resample BOTH variants independently, then take percentiles of their changes.

    A resample has the same size as its original sample. Sampling *with
    replacement* allows measurements to repeat; we do not invent new timings.
    More resamples reduce numerical randomness, not uncertainty in the data.
    A seed makes the output repeatable. No round-number pairing is assumed.
    """
    if type(resamples) is not int or resamples < 1:
        raise ValueError("resamples must be a positive integer")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 < confidence < 1:
        raise ValueError("confidence must lie between 0 and 1")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    a, b = np.asarray(baseline, dtype=float), np.asarray(comparison, dtype=float)
    if a.ndim != 1 or b.ndim != 1 or any(np.any(~np.isfinite(x)) or np.any(x < 0) for x in (a, b)):
        raise ValueError("timings must be finite, nonnegative, one-dimensional samples")
    result = {"baseline_n": len(a), "comparison_n": len(b), "percent": np.nan,
              "ci_low": np.nan, "ci_high": np.nan, "status": "missing_data"}
    if not len(a) or not len(b):
        return result
    reference = np.median(a)
    if reference <= 0:
        result["status"] = "zero_baseline_median"
        return result
    # The dot on the chart is always the estimate from the ORIGINAL data.
    result["percent"] = float(100 * (np.median(b) / reference - 1))
    if min(len(a), len(b)) < 2:
        result["status"] = "insufficient_samples"
        return result
    rng = np.random.default_rng(seed)
    changes = []
    # Work in small chunks so memory does not grow as resamples * sample size.
    for start in range(0, resamples, 1000):
        count = min(1000, resamples - start)
        # Step 1: independently draw replacement samples of each original size.
        sampled_a = rng.choice(a, size=(count, len(a)), replace=True)
        sampled_b = rng.choice(b, size=(count, len(b)), replace=True)
        # Step 2: recompute BOTH medians for every new pair of samples.
        medians_a = np.median(sampled_a, axis=1)
        medians_b = np.median(sampled_b, axis=1)
        if np.any(medians_a <= 0):
            # Dropping undefined ratios would silently change the distribution.
            result["status"] = "zero_resampled_baseline_median"
            return result
        changes.extend(100 * (medians_b / medians_a - 1))
    # Step 3: for 95% confidence, retain the middle 95% (2.5th--97.5th
    # percentiles) of the estimated changes. This is the percentile method.
    tail = (1 - confidence) / 2
    low, high = np.quantile(changes, [tail, 1 - tail])
    result.update(ci_low=float(low), ci_high=float(high), status="ok")
    return result


def summarize_bootstrap(baseline, comparison, queries, metric, **options):
    """One row per query; stable seeds keep results independent of pagination.

    Query and metric identify a random stream. Reordering queries, selecting a
    subset, or changing chart page size therefore leaves each interval intact.
    """
    settings = {**DEFAULTS, **options}
    rows = []
    for query in queries:
        identity = f'{settings["seed"]}:{metric}:{query}'.encode("utf-8")
        query_seed = int.from_bytes(hashlib.sha256(identity).digest()[:8], "little")
        result = bootstrap_median_change(
            values(baseline, query, metric).dropna().to_numpy(),
            values(comparison, query, metric).dropna().to_numpy(),
            **{**settings, "seed": query_seed})
        rows.append({"query": query, **result})
    return pd.DataFrame(rows).set_index("query")
