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
- `output_dir`: root for timestamped batches (default: `../generated/benchmark-comparisons`).
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

The implementation separates data loading and statistics (`benchmark_data.py`),
rendering (`benchmark_figures.py`), batch naming/export (`benchmark_output.py`), and configuration/orchestration
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

## Output batches and static index

```text
generated/benchmark-comparisons/
    index.html
    batches/
        2026-10-30T14-32-08Z_baseline__vs__mat-join/
            manifest.json
            change/
            rounds/
            metric_comparison.png
            metric_relationships.png
            duration_exceedance.png
```

Each invocation publishes a fresh batch directly under `batches/`. No directory
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
python3 scripts/benchmark_index.py
```

To migrate legacy nested batches into the flat structure and rebuild:

```bash
python3 scripts/benchmark_index.py --migrate
```

Migration moves completed batches, preserving image bytes, manifests, and batch
IDs; it removes only empty old hierarchy directories. Existing images are not
rewritten, so historical captions may refer to the former metadata sheet.

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
node scripts/test_benchmark_index.js
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
| `code` | File-content SHA-256 hashes of `benchmark_data.py`, `benchmark_figures.py`, `benchmark_output.py`, and `plot_benchmarks.py` |
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
