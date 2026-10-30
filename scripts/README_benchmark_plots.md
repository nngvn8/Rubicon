# Benchmark comparison plots

Compare one baseline execution with one comparison execution in the nested
benchmark format (`metadata` and `queries`). The old plotting scripts remain
available for legacy JSON files.

Install dependencies in your Python environment if needed:

```bash
python3 -m pip install -r scripts/requirements-plotting.txt
```

Run from the repository root:

```bash
python3 scripts/plot_benchmarks.py --config scripts/benchmark_plot_config.json
```

All configuration paths are relative to the configuration file. Set `baseline`
and `comparison` to experiment directories containing `results.json`; labels
are explicit and are never inferred from directory names. The supplied example
compares materialization outside joins (`Unmerged`) with materialization merged
into joins (`Merged`). Change the labels for other experiments.

Configuration options:

- `metrics`: any of `total_response_time`, `plan_duration`, `operator_work`.
  Defaults to response time. Operator work is cumulative instrumented operator
  duration, rather than elapsed plan time.
- `queries`: null for all queries, or a list of exact plan filenames including
  `.pb`. Queries use natural numeric ordering.
- `plots`: any of `change`, `distribution`, `rounds`, `metric_comparison`, `metric_relationships`; defaults to `change`, `rounds`, `metric_comparison`, and `metric_relationships`. Add `distribution` explicitly to generate it.
- `queries_per_page`: distribution/round panels per page; defaults to 6.
- `change_queries_per_page`: queries per change chart; defaults to 13
  (13 horizontal intervals).
- `output_dir`: figure destination. Outputs use metric, plot type, and page
  number; rerunning overwrites matching files. Remove obsolete pages yourself
  when narrowing a comparison.

Distribution panels overlay individual observations on boxplots (median,
25th–75th percentiles, whiskers within 1.5 IQR). Every observation is shown,
including outliers. Single observations appear as points. Round panels retain
actual measured round numbers and leave gaps for failures or missing metrics.
Matching round numbers across experiments do not imply paired measurements.

The tool rejects different query sets, worker counts, or scale factors. It
reports differences in host, warmups, query order, variants, plan source, and
restart policy. Failure counts and incomplete sample counts are printed;
failures are not replaced with timings. Warmup observations are not stored in
this benchmark format. Stored summaries are ignored in favor of raw samples.

The implementation separates data loading and statistics (`benchmark_data.py`),
rendering (`benchmark_figures.py`), and configuration/orchestration
(`plot_benchmarks.py`). `METRICS` defines shared labels and units. To add a plot,
add a rendering function and register its name in the CLI.

Run focused data and configuration checks:

```bash
python3 -m unittest discover -s scripts -p 'test_benchmark_plots.py'
```

The change chart shows one horizontal box-and-whisker interval per query.
For every combination of one baseline timing and one comparison timing, it
calculates `100 * (comparison / baseline - 1)`. Negative means faster. This
uses both empirical timing distributions without assuming matching rounds are
paired. The combinations reuse observations; they are not independent samples.
Labels report original sample counts (baseline/comparison), not pair counts.

The line and label show the median of these changes; the box spans the
25th–75th percentiles and whiskers span the 5th–95th percentiles. Tail values
outside that range are omitted from the display, not removed before calculating
quantiles. These are descriptive ranges, not confidence intervals, guaranteed
best/worst cases, or bounds on future measurements. The median can differ from
a percentage change calculated from the two timing medians.
The shaded ±2% region marks measurement tolerance. A violin is intentionally
avoided: estimating a smooth density from 20 timings adds detail without more
independent evidence. Zero baseline observations and absent samples make the
interval unavailable. Single observations yield a collapsed interval.

All round panels show `100 * (round value / baseline median - 1)`
for both plan types, using one shared reference per query. Dashed colored lines
mark each type's median; gray shading marks ±2% of the baseline median as a
practical relevance threshold, not a confidence interval. Each subtitle records
the absolute baseline median. Missing/zero baseline medians make the relative
panel unavailable.

Change whisker endpoints are annotated with signed absolute duration differences
using automatic units and three significant digits. These deltas come from the
same ranked timing combinations (and interpolation) as the percentage endpoints,
rather than independently calculated absolute-difference percentiles.

`metric_comparison` generates one `metric_comparison.png` with all selected queries
and metrics, without pagination. Each colored marker is the same median unpaired
percentage change shown in the corresponding change chart. Gray lines connect
the lowest and highest metric values per query; gray shading marks ±2%. Marker
shapes distinguish overlapping metrics. This overview omits variability intervals;
use the individual change charts for those. Missing metrics are flagged per row.

`metric_relationships` generates one `metric_relationships.png` with baseline and
comparison panels, identical percentage axes, and all selected queries. Each
metric is summarized by its median first, then normalized as
`100 * (median metric / median plan duration - 1)` within its own experiment.
Plan duration is zero; positive values indicate larger durations/work. Query
labels include absolute median plan duration. This compares within-type ordering
and spacing, while `metric_comparison` retains the between-type change view.
Missing or zero reference medians are unavailable.

Absolute duration labels in metric relationships use three significant digits
and one shared unit across both panels where practical. Values down to 0.1 of
that unit are allowed to avoid mixing seconds and milliseconds.

`duration_exceedance` (enabled by default) generates one `duration_exceedance.png`
with one horizontal bar per query in separate baseline/comparison panels. Bar
length is the count of rounds where `plan_duration > operator_work`; annotations
show count/eligible rounds and percentage. Only same-round samples containing
both metrics enter the denominator. Equality does not count; the 2% relevance
threshold is deliberately not applied to this invariant check.
