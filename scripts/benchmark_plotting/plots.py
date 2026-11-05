"""Render simple comparisons from normalized benchmark observations."""
from __future__ import annotations

import math
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter, MaxNLocator, PercentFormatter
import numpy as np

from data import METRICS, values

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
    """One comparison timing interval per query, relative to the baseline median."""
    from data import summarize_changes

    data = summarize_changes(*experiments, queries, metric)
    fig, ax = plt.subplots(figsize=(12, max(5, len(queries) * .48 + 2)))
    ax.axvspan(-2, 2, color="grey", alpha=.12)
    for i, (query, row) in enumerate(data.iterrows()):
        if not math.isfinite(row["median"]):
            ax.text(0, i, "unavailable (missing data or zero baseline median)", va="center", fontsize=8)
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
    ax.set_xlabel("Time change relative to baseline median (%) · negative = faster")
    ax.set_title(f'{METRICS[metric]["label"]}: {experiments[1].label} vs {experiments[0].label}')
    ax.grid(axis="x", alpha=.2)
    fig.text(.5, .02, "Line/label: percentage change between timing medians · Box: middle 50% · Whiskers: 5th–95th percentiles\n"
             "Comparison timing spread relative to baseline median; not confidence intervals · Shading: ±2% tolerance",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, 1))
    return fig


def plot_change_ci(experiments, queries, metric, *, summary=None, resamples=10000, confidence=.95, seed=0):
    """Separate uncertainty chart: point estimate plus bootstrap confidence interval."""
    from bootstrap import summarize_bootstrap

    if summary is None:
        summary = summarize_bootstrap(*experiments, queries, metric,
                                      resamples=resamples, confidence=confidence, seed=seed)
    fig, ax = plt.subplots(figsize=(12, max(5, len(queries) * .52 + 2)))
    ax.axvspan(-2, 2, color="grey", alpha=.12)
    ax.axvline(0, color="black", linewidth=.8)
    for i, (query, row) in enumerate(summary.iterrows()):
        if math.isfinite(row["percent"]):
            ax.plot(row["percent"], i, "o", color="tab:blue", zorder=3)
        if row["status"] == "ok":
            # Draw endpoints directly: percentile intervals need not contain
            # the original point estimate, so errorbar distances can be negative.
            ax.hlines(i, row["ci_low"], row["ci_high"], color="tab:blue", linewidth=2)
            ax.vlines([row["ci_low"], row["ci_high"]], i-.10, i+.10, color="tab:blue")
            label = f'{row["percent"]:+.2f}% [{row["ci_low"]:+.2f}, {row["ci_high"]:+.2f}]'
        else:
            label = f'CI unavailable: {row["status"].replace("_", " ")}'
        ax.text(1.02, i, label, transform=ax.get_yaxis_transform(), va="center", fontsize=8)
    ax.set_yticks(range(len(queries)), [f'{q.removesuffix(".pb")} (n={int(summary.loc[q, "baseline_n"])}/{int(summary.loc[q, "comparison_n"])})' for q in queries])
    ax.invert_yaxis()
    ax.set_xlabel("Change between timing medians (%) · negative = faster")
    ax.set_title(f'{METRICS[metric]["label"]}: {experiments[1].label} vs {experiments[0].label}')
    ax.grid(axis="x", alpha=.2)
    ax.margins(x=.1)
    fig.text(.5, .02,
             f'Dot: observed median change · Line: {confidence:.0%} percentile-bootstrap CI · {resamples:,} resamples · Shading: ±2% tolerance\n'
             'Exploratory: assumes independent samples; excludes between-session variation and execution-order bias',
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .07, .78, 1))
    return fig


def plot_metric_comparison(experiments, queries, metrics):
    """Compare the same median changes as the interval charts on one shared axis."""
    from data import summarize_changes

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
    ax.set_xlabel("Change between timing medians (%) · negative = lower / faster")
    ax.set_title(f'Metric comparison: {experiments[1].label} vs {experiments[0].label}')
    ax.grid(axis="x", alpha=.2)
    ax.grid(axis="y", alpha=.1)
    ax.margins(x=.15)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.09), ncol=len(metrics), fontsize=9)
    fig.text(.5, .02, "Dots: percentage changes between timing medians · Lines: span between metrics · Shading: ±2% tolerance", ha="center", fontsize=9)
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
    from data import duration_exceedance_counts
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



def plot_cross_scale(pairs, queries, metric, scaling_interval, color_limits=(-20, 20)):
    """Changes between medians at each scale, alongside scaling ratios of medians."""
    from data import summarize_changes
    from matplotlib.colors import TwoSlopeNorm

    scales = sorted(pairs)
    heat = np.array([summarize_changes(*pairs[sf], queries, metric)["median"].to_numpy()
                     for sf in scales]).T
    lower, upper = color_limits
    height = max(5, .48 * len(queries) + 2)
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, height),
                                     gridspec_kw={"width_ratios": [max(1, len(scales) / 3), 1.2]})
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#eeeeee")
    heatmap = left.imshow(np.ma.masked_invalid(heat), aspect="auto", cmap=cmap,
                          norm=TwoSlopeNorm(vmin=lower, vcenter=0, vmax=upper))
    colorbar = fig.colorbar(heatmap, ax=left, fraction=.035, pad=.025, extend="both")
    colorbar.set_label("Change (%) · colors clipped at limits")
    left.set_xticks(range(len(scales)), [f"SF {sf:g}" for sf in scales])
    labels = [q.removesuffix(".pb") for q in queries]
    left.set_yticks(range(len(queries)), labels)
    for row in range(len(queries)):
        for column in range(len(scales)):
            value = heat[row, column]
            text = f"{value:+.1f}%" if np.isfinite(value) else "N/A"
            left.text(column, row, text, ha="center", va="center",
                      color="white" if np.isfinite(value) and (value > .6 * upper or value < .6 * lower) else "#17212b")
    left.set_title("Effect of merging" if [e.label.lower() for e in pairs[scales[0]]] == ["unmerged", "merged"]
                   else f"{pairs[scales[0]][1].label} vs {pairs[scales[0]][0].label}")
    left.set_xlabel("Percentage change between timing medians\nNegative (blue) = lower; positive (red) = higher")

    low, high = scaling_interval
    expected = high / low
    positions = np.arange(len(queries))
    plotted = [expected]
    for i, offset in enumerate((-.13, .13)):
        ratios = []
        for row, query in enumerate(queries):
            before = values(pairs[low][i], query, metric).dropna().median()
            after = values(pairs[high][i], query, metric).dropna().median()
            ratio = after / before if math.isfinite(before) and before > 0 and math.isfinite(after) else np.nan
            ratios.append(ratio)
            if math.isfinite(ratio):
                right.annotate(f"{ratio:.2f}×", (ratio, row + offset), xytext=(6, 0),
                               textcoords="offset points", va="center", fontsize=8, color=COLORS[i])
            else:
                right.text(.99, row + offset, f"{pairs[low][i].label}: N/A", transform=right.get_yaxis_transform(),
                           ha="right", va="center", fontsize=8, color=COLORS[i])
        right.scatter(ratios, positions + offset, color=COLORS[i], label=pairs[low][i].label, s=40)
        plotted.extend(value for value in ratios if math.isfinite(value))
    right.axvline(expected, color="#555555", linestyle="--", linewidth=1.2,
                  label=f"Linear scaling ({expected:g}×)")
    span = max(max(plotted) - min(plotted), .1 * max(plotted), .1)
    right.set_xlim(min(plotted) - .12 * span, max(plotted) + .4 * span)
    right.set_yticks(positions, labels)
    right.set_ylim(len(queries) - .5, -.5)
    right.set_title(f"Scaling from SF {low:g} to SF {high:g}")
    right.set_xlabel(f"Median {METRICS[metric]['label'].lower()}: SF {high:g} / SF {low:g}\n"
                     "Further right = larger runtime multiplier")
    right.grid(axis="x", alpha=.2)
    # Keep legends outside the query rows, including for extreme scaling values.
    right.legend(loc="lower center", bbox_to_anchor=(.5, 1.07), ncol=3, fontsize=8)
    first = pairs[scales[0]][0].metadata
    mode = first.get("execution_mode", "execution mode not recorded")
    fig.suptitle(f"{METRICS[metric]['label']} across scale factors · {mode} · "
                 f"{first['workers_per_cu']} workers")
    fig.text(.5, .015, "Left: percentage changes between medians · "
             "Right: ratios of medians · N/A: missing data or zero denominator", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .055, 1, .90))
    return fig
