"""Render simple comparisons from normalized benchmark observations."""
from __future__ import annotations

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter, MaxNLocator, PercentFormatter
import numpy as np

from benchmark_data import METRICS, values

COLORS = ("tab:blue", "tab:orange")


def plot_panels(experiments, queries, metric, kind):
    relative = kind == "rounds"
    columns = min(3, len(queries))
    fig, axes = plt.subplots(math.ceil(len(queries) / columns), columns, figsize=(5 * columns, 3.5 * math.ceil(len(queries) / columns)), squeeze=False)
    for ax, query in zip(axes.flat, queries):
        reference = values(experiments[0], query, metric).dropna().median() if relative else None
        if relative:
            ax.set_title(query.removesuffix(".pb"))
            ax.set_ylabel("Change from baseline median")
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
            if not math.isfinite(reference) or reference <= 0:
                ax.text(.5, .5, "Unavailable: missing or zero baseline median",
                        transform=ax.transAxes, ha="center", va="center", wrap=True)
                continue
            ax.axhspan(-2, 2, color="grey", alpha=.12)
        for i, experiment in enumerate(experiments):
            series = values(experiment, query, metric)
            observed = series.dropna()
            label = f"{experiment.label} (n={len(observed)})"
            if kind == "distribution":
                if len(observed) > 1:
                    ax.boxplot([observed.to_numpy()], positions=[i], widths=.45, showfliers=False, medianprops={"color": COLORS[i]}, whiskerprops={"color": COLORS[i]}, boxprops={"color": COLORS[i]})
                # Deterministic offsets keep overlapping points visible.
                offsets = np.random.default_rng(i).uniform(-.12, .12, len(observed))
                ax.scatter(i + offsets, observed, color=COLORS[i], s=16, alpha=.65)
                ax.set_xticks([0, 1], [f"{e.label}\n(n={values(e, query, metric).count()})" for e in experiments])
            else:
                complete = series.reindex(range(1, experiment.metadata["measured_rounds"] + 1))
                if relative:
                    complete = 100 * (complete / reference - 1)
                    if len(observed):
                        median = 100 * (observed.median() / reference - 1)
                        ax.axhline(median, color=COLORS[i], linestyle="--", linewidth=1, alpha=.8)
                ax.plot(complete.index, complete, marker="o", markersize=3, color=COLORS[i], label=label)
                ax.set_xlabel("Measured round")
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
                ax.legend(fontsize=8)
        if relative:
            ax.set_title(f'{query.removesuffix(".pb")}\n{experiments[0].label} median: {EngFormatter(unit="s", places=3)(reference)}', fontsize=10)
        else:
            ax.set_title(query.removesuffix(".pb"))
            ax.set_ylabel(METRICS[metric]["label"])
            ax.yaxis.set_major_formatter(EngFormatter(unit=METRICS[metric]["unit"]))
        ax.grid(axis="y", alpha=.2)
    for ax in list(axes.flat)[len(queries):]:
        ax.set_visible(False)
    fig.suptitle(f'{METRICS[metric]["label"]} · {kind} · {experiments[0].label} vs {experiments[1].label}')
    if relative:
        fig.text(.5, .02, "Shared reference: baseline median · Dashed lines: plan-type medians · Shading: ±2% relevance threshold (not a confidence interval)", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .05 if relative else 0, 1, .96))
    return fig


def format_delta(seconds):
    """Signed duration with three significant digits, preserving trailing zeros."""
    if seconds == 0:
        return "0 s"
    units = ((1e-12, "ps"), (1e-9, "ns"), (1e-6, "µs"), (1e-3, "ms"), (1, "s"), (1e3, "ks"))
    scale, unit = units[0]
    for candidate, name in units:
        if abs(seconds) >= candidate:
            scale, unit = candidate, name
    rounded = float(f"{seconds / scale:.3g}")
    for candidate, name in units:
        if candidate > scale and abs(rounded) >= 1000:
            scale, unit = candidate, name
            rounded = float(f"{seconds / scale:.3g}")
            break
    decimals = max(0, 2 - math.floor(math.log10(abs(rounded))))
    return f"{rounded:+.{decimals}f} {unit}"


def plot_change(experiments, queries, metric):
    """One horizontal empirical time-change interval per query."""
    from benchmark_data import summarize_changes

    data = summarize_changes(*experiments, queries, metric)
    fig, ax = plt.subplots(figsize=(12, max(5, len(queries) * .48 + 2)))
    ax.axvspan(-2, 2, color="grey", alpha=.12)
    for i, (query, row) in enumerate(data.iterrows()):
        if not math.isfinite(row["median"]):
            ax.text(0, i, "unavailable (missing data or zero baseline)", va="center", fontsize=8)
            continue
        ax.bxp([{
            "med": row["median"], "q1": row["q1"], "q3": row["q3"],
            "whislo": row["p05"], "whishi": row["p95"], "fliers": [],
        }], positions=[i], vert=False, widths=.4, showfliers=False,
            manage_ticks=False, patch_artist=True,
            boxprops={"facecolor": "tab:blue", "alpha": .3},
            medianprops={"color": "black", "linewidth": 1.5},
            whiskerprops={"color": "tab:blue"}, capprops={"color": "tab:blue"})
        ax.annotate(f'{row["median"]:+.2f}%', (row["median"], i),
                    xytext=(0, 10), textcoords="offset points", ha="center", fontsize=8)
        for endpoint, offset, alignment in (("p05", -5, "right"), ("p95", 5, "left")):
            ax.annotate(format_delta(row[f"{endpoint}_delta"]), (row[endpoint], i),
                        xytext=(offset, 0), textcoords="offset points",
                        ha=alignment, va="center", fontsize=8)
    ax.set_yticks(range(len(queries)), [f'{q.removesuffix(".pb")} (n={int(data.loc[q, "baseline_n"])}/{int(data.loc[q, "comparison_n"])})' for q in queries])
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=.8)
    ax.margins(x=.23)
    ax.set_xlabel("Time change relative to baseline (%) · negative = faster")
    ax.set_title(f'{METRICS[metric]["label"]}: {experiments[1].label} vs {experiments[0].label}')
    ax.grid(axis="x", alpha=.2)
    fig.text(.5, .02, "Line/label: median · Box: middle 50% · Whiskers: 5th–95th percentiles · Shading: ±2% tolerance\n"
             "All unpaired timing combinations; descriptive variation, not confidence intervals or absolute bounds.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, 1))
    return fig


def plot_metric_comparison(experiments, queries, metrics):
    """Compare the same median changes as the interval charts on one shared axis."""
    from benchmark_data import summarize_changes

    medians = {metric: summarize_changes(*experiments, queries, metric)["median"] for metric in metrics}
    fig, ax = plt.subplots(figsize=(12, max(5, len(queries) * .5 + 2)))
    ax.axvspan(-2, 2, color="grey", alpha=.12)
    for i, query in enumerate(queries):
        finite = [series.loc[query] for series in medians.values() if math.isfinite(series.loc[query])]
        if finite:
            ax.hlines(i, min(finite), max(finite), color="grey", linewidth=1.5, zorder=2)
        if len(finite) != len(metrics):
            ax.annotate("missing metric(s)", (1, i), xycoords=("axes fraction", "data"), xytext=(5, 0), textcoords="offset points", fontsize=8, va="center")
    # Different shapes and slightly different sizes keep nearly identical values visible.
    styles = dict(zip(METRICS, (("tab:blue", "o", 70), ("tab:orange", "D", 38), ("tab:purple", "^", 50))))
    for metric in metrics:
        color, marker, size = styles[metric]
        ax.scatter(medians[metric], range(len(queries)), color=color, marker=marker,
                   s=size, label=METRICS[metric]["label"], zorder=3, edgecolors="white", linewidths=.5)
    ax.set_yticks(range(len(queries)), [query.removesuffix(".pb") for query in queries])
    ax.invert_yaxis()
    ax.axvline(0, color="black", linewidth=.8)
    ax.set_xlabel("Median change relative to baseline (%) · negative = lower / faster")
    ax.set_title(f'Metric comparison: {experiments[1].label} vs {experiments[0].label}')
    ax.grid(axis="x", alpha=.2)
    ax.grid(axis="y", alpha=.1)
    ax.margins(x=.15)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.09), ncol=len(metrics), fontsize=9)
    fig.text(.5, .02, "Dots: median of unpaired percentage changes · Lines: span between metrics · Shading: ±2% tolerance", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, 1))
    return fig


def duration_label_scale(durations):
    """Choose a shared engineering unit, allowing one leading fractional zero."""
    finite = [value for value in durations if math.isfinite(value) and value > 0]
    if not finite:
        return 1, "s"
    units = ((1e-12, "ps"), (1e-9, "ns"), (1e-6, "µs"), (1e-3, "ms"), (1, "s"), (1e3, "ks"))
    candidates = [(scale, unit) for scale, unit in units
                  if min(finite) / scale >= .1 and max(finite) / scale < 999.5]
    if candidates:
        return candidates[-1]
    # Large ranges may not fit a single compact unit; retain a shared unit
    # based on the typical duration rather than mixing units across labels.
    typical = float(np.median(finite))
    return next(((scale, unit) for scale, unit in reversed(units) if typical >= scale), units[0])


def format_duration_label(seconds, scale, unit):
    if not math.isfinite(seconds) or seconds <= 0:
        return "unavailable"
    rounded = float(f"{seconds / scale:.3g}")
    decimals = max(0, 2 - math.floor(math.log10(abs(rounded))))
    return f"{rounded:.{decimals}f} {unit}"


def plot_metric_relationships(experiments, queries, metrics):
    """Compare within-experiment metric medians relative to median plan duration."""
    fig, axes = plt.subplots(1, 2, figsize=(16, max(6, len(queries) * .5 + 2)), sharex=True)
    styles = dict(zip(METRICS, (("tab:blue", "o", 70), ("tab:orange", "D", 38), ("tab:purple", "^", 50))))
    references = {(index, query): values(experiment, query, "plan_duration").dropna().median()
                  for index, experiment in enumerate(experiments) for query in queries}
    scale, unit = duration_label_scale(references.values())
    for index, (ax, experiment) in enumerate(zip(axes, experiments)):
        positions = {metric: [] for metric in metrics}
        labels = []
        for i, query in enumerate(queries):
            reference = references[index, query]
            valid_reference = math.isfinite(reference) and reference > 0
            absolute = format_duration_label(reference, scale, unit)
            labels.append(f'{query.removesuffix(".pb")} · {absolute}')
            for metric in metrics:
                median = values(experiment, query, metric).dropna().median()
                positions[metric].append(100 * (median / reference - 1) if valid_reference else float("nan"))
            finite = [positions[metric][-1] for metric in metrics if math.isfinite(positions[metric][-1])]
            if finite:
                ax.hlines(i, min(finite), max(finite), color="grey", linewidth=1.5, zorder=2)
            if len(finite) != len(metrics):
                ax.annotate("unavailable metric(s)", (1, i), xycoords=("axes fraction", "data"), xytext=(-4, 0), textcoords="offset points", ha="right", va="center", fontsize=7)
        for metric in metrics:
            color, marker, size = styles[metric]
            ax.scatter(positions[metric], range(len(queries)), color=color, marker=marker,
                       s=size, label=METRICS[metric]["label"], zorder=3, edgecolors="white", linewidths=.5)
        ax.set_yticks(range(len(queries)), labels)
        ax.invert_yaxis()
        ax.axvline(0, color="black", linewidth=.8)
        ax.axvspan(-2, 2, color="grey", alpha=.12)
        ax.grid(axis="x", alpha=.2)
        ax.grid(axis="y", alpha=.1)
        ax.margins(x=.15)
        ax.set_title(experiment.label)
        ax.set_xlabel("Difference from own median plan duration (%)")
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=100))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .04), ncol=len(metrics))
    fig.suptitle("Metric relationships within each plan type")
    fig.text(.5, .015, "Markers: ratios of metric medians · Query labels: absolute median plan duration · Shading: ±2% tolerance", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .1, 1, .96))
    return fig


def plot_duration_exceedance(experiments, queries, metrics=None):
    """One count bar per query and experiment, annotated with relative frequency."""
    from benchmark_data import duration_exceedance_counts
    from matplotlib.ticker import MultipleLocator

    summaries = [duration_exceedance_counts(experiment, queries) for experiment in experiments]
    maximum = max(1, *(int(data["count"].max()) for data in summaries))
    fig, axes = plt.subplots(1, 2, figsize=(15, max(5, len(queries) * .45 + 2)), sharex=True)
    for ax, experiment, data, color in zip(axes, experiments, summaries, COLORS):
        ax.barh(range(len(queries)), data["count"], color=color, height=.6)
        for i, row in enumerate(data.itertuples()):
            label = f"{row.count}/{row.total} ({row.percent:.1f}%)" if row.total else "unavailable (no complete rounds)"
            ax.annotate(label, (row.count, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=9)
        ax.set_yticks(range(len(queries)), [q.removesuffix(".pb") for q in queries])
        ax.invert_yaxis()
        ax.set_xlim(0, maximum * 1.35 + 1)
        ax.xaxis.set_major_locator(MultipleLocator(max(1, math.ceil(maximum / 5))))
        ax.set_xlabel("Number of rounds")
        ax.set_title(experiment.label)
        ax.grid(axis="x", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle("Rounds where plan duration exceeds operator work")
    fig.text(.5, .025, "Strict comparison within each round · Labels: count / rounds with both metrics (relative frequency) · No 2% tolerance applied", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .96))
    return fig
