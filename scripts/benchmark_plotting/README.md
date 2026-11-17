# Benchmark comparison plots

Compare one baseline execution with one comparison execution in the nested
benchmark format (`metadata` and `queries`). The old plotting scripts remain
available for legacy JSON files.

Install dependencies in your Python environment if needed:

```bash
python3 -m pip install -r scripts/benchmark_plotting/requirements.txt
```

Run from the repository root:

```bash
python3 scripts/benchmark_plotting/plot_benchmarks.py --config scripts/benchmark_plotting/config.json
```

The supplied configurations are separated by purpose:

- `config.json`: normal plots comparing concurrent Unmerged/Merged runs at SF 100,
  using all three timing metrics.
- `config_cross_scale.json`: only the cross-scale figure, using concurrent pairs
  at SF 2, 50 and 100; response time; SF 50→100 scaling interval.
- `config_template.json`: the previous combined configuration, retained as an
  example of generating normal and cross-scale plots together (sequential inputs).

Generate the concurrent cross-scale figure with:

```bash
python3 scripts/benchmark_plotting/plot_benchmarks.py --config scripts/benchmark_plotting/config_cross_scale.json
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
- `plots`: any of `change_ci`, `change`, `distribution`, `rounds`, `metric_comparison`, `metric_relationships`, and `duration_exceedance`; these are enabled by default except `distribution`.
  The optional `cross_scale` plot requires its own input-pair section below.
- `queries_per_page`: distribution/round panels per page; defaults to 6.
- `change_queries_per_page`: queries per change chart; defaults to 13
  (13 horizontal intervals).
- `output_dir`: fixed to the repository’s `benchmarking/plots/runtime`; batches are written directly beneath it. Omit this field to use that location regardless of where the config lives.
- `baseline.id` / `comparison.id`: optional short comparison identifiers.
- `name`: optional batch-description override, replacing the derived comparison name.
  Overrides accept filename characters only, without directory separators.

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

The implementation separates data loading and statistics (`data.py`),
rendering (`plots.py`), configuration and batch export (`plot_benchmarks.py`),
and the HTML results browser (`index.py` and `index.html`). `METRICS` defines shared labels and units. To add a plot,
add a rendering function and register its name in the CLI.

Run focused data and configuration checks:

```bash
python3 -m unittest discover -s scripts/benchmark_plotting/tests
```

## RAM timelines

RAM collection exports data only. Render a recorded session afterward:

```bash
python3 scripts/benchmark_plotting/plot_memory.py /path/to/benchmark-session
```

The input may also be that session's `results.json` or `memory_summary.json`.
The command reads `memory_samples.csv` and `memory_summary.json` without changing
them. It writes `memory.png` and a source-fingerprinted `manifest.json` into a
new batch under `benchmarking/plots/memory/`. Use `--output-dir PATH` to choose
another output parent. Regenerating a plot creates a new batch.

The top panel shows whole-CU RSS, its fixed baseline, and round boundaries.
The lower panel shows plan intervals per query and clock-aligned operator
segments; warmup plans are faded. Large sampling gaps break the RSS curve.
Execution intervals show concurrent activity, not ownership of resident memory.
Absolute and baseline-relative integrals remain in `memory_summary.json`;
overlapping window integrals must not be summed. RAM plotting is separate from
the two-experiment timing-comparison configuration and browser.

All percentage-change summaries compare the two timing medians:
`100 * (median(comparison) / median(baseline) - 1)`. Negative means faster.
This applies to change labels, metric-comparison markers, and cross-scale
heatmap cells. No Cartesian product or round pairing is used.

The change chart shows one blue horizontal box-and-whisker interval per query
for the comparison variant, normalized against the baseline median:
`100 * (comparison timing / baseline median - 1)`. The line and label equal
the percentage change between the two timing medians. Labels report original
sample counts (baseline/comparison). Boxes span the comparison's 25th–75th
percentiles and whiskers span its 5th–95th percentiles. These describe comparison
timing spread relative to the fixed baseline median, not confidence intervals
for the median change or bounds on future measurements. Tail observations
outside the whiskers are retained when calculating medians and quantiles. The
shaded ±2% region marks practical tolerance. A zero baseline median or absent
samples makes the change unavailable; individual zero timings remain valid when
that median is positive. Single observations yield collapsed intervals.

`change_ci` is an optional, separate confidence-interval chart. The existing
`change` chart continues to show timing spread. Enable it with:

```json
"plots": ["change_ci"],
"bootstrap": {"resamples": 10000, "confidence": 0.95, "seed": 0}
```

The dot is the observed percentage change between medians. The line is an
**exploratory percentile-bootstrap confidence interval**. The recipe is:

1. Draw a replacement sample from the baseline, of the original baseline size.
2. Independently draw a replacement sample from the comparison, of its size.
3. Recalculate both medians and `100 * (comparison median / baseline median - 1)`.
4. Repeat 10,000 times. For a 95% interval, use the 2.5th and 97.5th percentiles
   of these changes. The interval need not be symmetric around the observed dot.

Both distributions influence the interval. Matching round numbers are **not**
paired. This simple method assumes independent, representative observations
within each input directory. It does not account for between-session variation,
serial dependence, warm-up, or differences in conditions between batches.
With 20 samples, treat the intervals as approximate; more resamples do not add
new experimental information. These are individual intervals per query/metric,
not simultaneous confidence statements for the whole collection.

The implementation in `bootstrap.py` follows these steps with comments. Seeds
are deterministic per query/metric, so pagination does not change results.
`bootstrap_summary.csv` contains the estimates, endpoints, sample counts, and
explicit availability status; the manifest records its path and method settings.
Missing samples, fewer than two samples per variant, a zero baseline median,
or any zero resampled baseline median make the CI unavailable. Undefined ratios
are never silently discarded. Constant samples can produce a collapsed interval;
that does not establish absence of variation outside the observed batch.

All round panels show `100 * (round value / baseline median - 1)`
for both plan types, using one shared reference per query. Dashed colored lines
mark each type's median; gray shading marks ±2% of the baseline median as a
practical relevance threshold, not a confidence interval. Each subtitle records
the absolute baseline median. Missing/zero baseline medians make the relative
panel unavailable.

Change whisker endpoints are annotated with signed absolute duration differences
using automatic units and three significant digits. Each delta is the corresponding
comparison timing quantile minus the baseline timing median, using the same
fixed reference as the percentage endpoints.

`metric_comparison` generates one `metric_comparison.png` with all selected queries
and metrics, without pagination. Each colored marker is the same percentage change between
timing medians shown in the corresponding change chart. Gray lines connect
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

## Output batches and static index

```text
benchmarking/plots/runtime/
    index.html
    2026-10-30T14-32-08Z_baseline__vs__mat-join/
        manifest.json
        change/
        rounds/
        metric_comparison.png
        metric_relationships.png
        duration_exceedance.png
```

Each invocation publishes a fresh batch directly under `plots/runtime/`. No directory
levels are added for workers, scale factor, optimizations, or execution mode.
Timestamps are UTC; collisions get numbered suffixes. Input metadata supplies
compact comparison names (`baseline`, `mat-join`, `mat-join-group`), with optional
input `id` or comparison `name` overrides. Names are convenient identifiers;
the manifest is the authoritative record of all settings.

The manifest records input metadata, complete paths, SHA-256 hashes, resolved
plotting configuration, queries, notices, generation time, and figure filenames.
Only complete batches are published; input changes during plotting reject the
batch. Figure captions retain recorded baseline/comparison settings and batch ID,
referring to `manifest.json` for full details. No separate `metadata.md` is created.

Plotting automatically rebuilds `index.html`. To rebuild without plotting:

```bash
python3 scripts/benchmark_plotting/index.py
```

Open the index as a static HTML page in your browser. It embeds its manifest
snapshot, filtering code, and styles: no Python server, database, network requests,
or dependencies are needed for browsing. Rebuild/reload it after new batches.
For a remote IDE, download/open the HTML locally or use your IDE's HTML preview
if it supports JavaScript. The index retains remote absolute directory paths.

The page provides full-text search and metadata filters. Add any recorded field,
including nested optimization flags or worker counts. Shared values appear once;
differences appear explicitly as baseline → comparison. Missing fields display
“Not recorded,” never inferred from directory names or prose. Full metadata is
expandable in each row, with a link to its manifest (available when opening the
index alongside its batch directories).

Collapsed editor settings choose Antigravity (default) or VS Code, remembering
the selection in browser storage where available. Each row copies a shell-quoted
`antigravity-ide -n '<remote-directory>'` or `code -n '<remote-directory>'` command.
Paste it into your remote IDE terminal to open a new window without adding
workspace roots. Clipboard fallback selects the command for manual copying.
The page does not execute commands or open editor windows itself.

Index interaction checks (if Node.js is available):

```bash
node scripts/benchmark_plotting/tests/test_index.js
```

## Grouping and chronology

**Group matching configurations** is enabled by default. Each collapsed group
shows its newest matching batch as a fully usable representative: its directory,
copy command, manifest, settings, and notices remain available without expansion.
Groups sort by that representative's generation time, newest first. Expanded
members also sort newest first. **Expand all**, **Collapse all**, and disabling
grouping provide detailed or ordinary chronological views. Filters apply before
grouping, so the representative is always the newest batch matching the filters.

The group key is a SHA-256 hash of canonical JSON containing baseline and
comparison metadata separately, preserving their direction. The key excludes:

- Benchmark `created_at` and `config_file` fields.
- `experiment.notes` and `experiment.reason`. If these were the only experiment
  fields, the resulting empty `experiment` object is omitted.

All other recorded fields remain significant, including host, query order,
worker count, scale factor, execution mode, optimization settings, warmup policy,
restart policy, plan source, and unknown future settings. Structured experiment
settings are retained. Missing fields and explicit false values differ. Plotting
settings and selected plot types are not part of metadata grouping: expanding
may reveal multiple renderings of the same experimental configuration.

## Rendering fingerprints and redundant batches

New plotting runs record `rendering.sha256` and `rendering.payload` in their
manifest. The digest is SHA-256 over UTF-8 canonical JSON (`sort_keys=True`,
`separators=(",", ":")`, `ensure_ascii=True`, `allow_nan=False`). The payload is:

| Key | Exact contents |
| --- | --- |
| `schema_version` | `1`; bump when the fingerprint rules change |
| `inputs` | Separate baseline and comparison SHA-256 hashes of complete input `results.json` bytes |
| `queries` | Resolved query selection in actual display order |
| `metrics` | Selected metric names in configured order |
| `plots` | Selected plot types, sorted (generation order alone is irrelevant) |
| `labels` | Baseline and comparison display labels |
| `pagination` | `queries_per_page` and `change_queries_per_page` |
| `code` | File-content SHA-256 hashes of `data.py`, `plots.py`, `plot_benchmarks.py`, `index.py`, and `cross_scale.py` |
| `environment` | Python, Matplotlib, NumPy, pandas and FreeType versions, plus the Matplotlib backend |

Input hashes include both timings and metadata. Therefore even JSON whitespace
changes can distinguish inputs; this deliberately favors missing a redundant
batch over incorrectly declaring different inputs equivalent. Query selection
must be included separately because one results file can supply multiple subsets.

Excluded: generation time, batch ID, input/output paths, optional naming aliases,
Git revision, file modification times, index/template code, editor choice, and
the documentation/tests. The generation ID and source-directory names printed
in captions are provenance annotations and intentionally do not distinguish
renderings. Thus redundant means equivalent under this schema, not byte-identical
PNG files. Unrecorded machine-level differences, such as available system fonts,
are not a pixel reproducibility guarantee.

The fingerprint is captured before plotting and rechecked before publication.
Changes to inputs, rendering code, or the recorded environment during plotting
reject the batch. At index generation, digest integrity, input hashes and resolved
plot settings are validated against the manifest. Editing those recorded settings
without regenerating invalidates fingerprint recognition.

### Index badges

- **Redundant** appears on older batches with the same verified rendering
  fingerprint. The newest equivalent batch is retained as the representative
  rendering (with timestamp ties broken deterministically by directory path).
- **Other renderings** links batches generated from the same ordered pair of
  resolved baseline/comparison directories, even when fingerprints differ or
  were never recorded. Equivalent fingerprints can also link copied input files
  at different paths. Matching paths alone never proves redundancy.
- Hover, focus, or click a badge to see related generation timestamps and the
  recorded differences: input contents, query selection/order, metrics/order,
  plot types, labels, pagination, plotting code, or environment. Links expand the
  target group and briefly highlight its row. Conflicting filters are cleared
  when necessary to reveal the target.

Legacy manifests have **Rendering fingerprint not recorded**. Their original
rendering code/environment cannot be reconstructed reliably, so rebuilding the
index never fabricates fingerprints for them. They remain eligible for metadata
 grouping and same-directory links, but never receive a Redundant flag solely
from those similarities. The current index does not delete files; redundancy
badges support an explicit decision to remove older batch directories. Rebuild
the index after any manual removal.


## Optional comparison across scale factors

Add `"cross_scale"` to `plots` and configure a `cross_scale` section in the same
JSON file. The supplied `config_cross_scale.json` selects only this figure and
includes the three November concurrent pairs (SF 2, 50 and 100), with response
time and the SF 50→100 scaling interval. `config_template.json` demonstrates
combining it with normal plots in one config. Remove `"cross_scale"` from `plots`
to disable the additional figure. No additional command-line flags are used;
the usual command reads all settings from the chosen file.

For example, a standalone cross-scale configuration can contain:

```json
{
  "baseline": {"label": "Unmerged"},
  "comparison": {"label": "Merged"},
  "plots": ["cross_scale"],
  "queries": null,
  "cross_scale": {
    "metric": "total_response_time",
    "scaling_interval": [50, 100],
    "pairs": [
      {"baseline": "relative/path/to/unmerged-sf2", "comparison": "relative/path/to/merged-sf2"},
      {"baseline": "relative/path/to/unmerged-sf50", "comparison": "relative/path/to/merged-sf50"},
      {"baseline": "relative/path/to/unmerged-sf100", "comparison": "relative/path/to/merged-sf100"}
    ]
  }
}
```

Each directory contains `results.json`; paths resolve relative to the config
file. Scale factors come from input metadata, not directory names or list order.
At least two pairs are required; any larger number is supported. Labels and
optional query selection are shared with ordinary plots. With only
`"cross_scale"` selected, root-level baseline/comparison directories are optional.
When combining it with ordinary plots, keep those directories for the existing
single-pair comparisons. A separate cross-scale batch is exported alongside the
ordinary batch.

`cross_scale.metric` accepts `total_response_time` (default), `plan_duration`,
or `operator_work`, independently of the ordinary `metrics` list.
`scaling_interval` selects two increasing scale factors present in the inputs;
omitting it selects the two largest. The dashed reference is their scale ratio,
so SF 2→50 uses 25× rather than a fixed 2× reference.

`cross_scale.color_limits` fixes the heatmap's color range, defaulting to
`[-20, 20]` percent, with zero centered. Use the same limits to compare sequential
and concurrent figures by color. Values beyond the limits use endpoint colors;
the actual numeric annotations remain unchanged. The color bar marks clipping
at both limits. Custom limits must be finite and span zero. Limits are recorded
in the configuration and rendering fingerprint.

The left panel uses the same percentage change between timing medians as the
existing change plots. Each variant is summarized by its median before taking
the ratio; no all-pairs comparisons are computed. Negative/blue means a lower
value for the comparison variant. The right panel divides the per-query median
at the higher scale by its median at the lower scale, independently per variant.
These two statistical definitions are deliberately explicit in the figure.

Validation rejects duplicate directories/scales, mismatching query sets,
within-pair scale or worker mismatches, and incompatible execution settings.
Within a pair, optimization and variant metadata may differ. Within each variant
across scales, all configuration metadata except scale factor must match,
including host, workers, execution mode, warmups, measured-round count, query
order, compilation, plan source, restart policy, optimization flags and unknown
future settings. Creation timestamps, config-file paths, and experiment prose
(`notes`/`reason`) are excluded; structured experiment settings remain checked.
Missing settings differ from explicitly recorded settings. Validation covers
all supplied pairs, even when only some queries or scales enter the right panel.

Failures, incomplete samples and zero values are retained as manifest notices.
Unavailable ratios appear as `N/A`; failures are never replaced with timings.
The heatmap is unavailable if the baseline median is zero or either median is missing. Scaling is
unavailable if the lower-scale median is zero or either median is missing.

Each cross-scale batch contains `cross_scale.png` and its own `manifest.json`.
The manifest's `scale_pairs` records every input's complete metadata, absolute
path and SHA-256, alongside resolved settings, query selection, notices, and
rendering code/environment hashes. Inputs and rendering dependencies are checked
again before atomic publication. The index shows the scale-factor list and full
per-input metadata, and groups cross-scale configurations separately from
ordinary comparisons. Rendering fingerprint schema 2 covers the metric, interval,
all input hashes, labels and query selection; pair ordering and storage paths do
not affect the fingerprint. Ordinary fingerprints retain schema 1.

To generate the exploratory bootstrap comparisons for every compatible merged /
unmerged execution under `benchmarking/data`, run from the repository root:

```bash
python3 scripts/benchmark_plotting/generate_bootstrap.py --inventory-only
python3 scripts/benchmark_plotting/generate_bootstrap.py
```

The driver excludes `archive`, `-O0`, and its own derived `bootstrap` data subtree.
It matches all recorded settings except timestamps, descriptive experiment notes,
and the merge switch being compared. Thus scale factor, execution mode
(sequential/concurrent), worker count, compilation settings, host, and other
optimization flags must agree. When multiple executions share settings, each
compatible unmerged/merged directory pair is rendered separately; samples are
never pooled or paired by round number across executions.

Canonical numeric results are saved in
`benchmarking/data/bootstrap/<run-id>/all_confidence_intervals.csv`. The adjacent
`coverage.json` records source directories, pairing settings, exclusions,
bootstrap settings, and output paths; the per-pair JSON configurations make
individual comparisons reproducible. The underlying input fingerprints and code
fingerprints are recorded in each plotting batch's manifest. Individual bootstrap
draws are not retained: the CSV contains the observed median changes and interval
endpoints. The linked overview is saved under
`benchmarking/plots/runtime/bootstrap-reports/<run-id>/index.html`.
The driver prints both locations when complete.
