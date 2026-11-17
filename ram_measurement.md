# RAM measurement plan

Status: Phase 1 implemented as optional collection in `experiments/run_query.py`. The broader ideas below remain documented for later work; allocation ownership tracking is not implemented.

## Goal and entry points

- Compare RAM consumption after changes to query plans and operator implementations.
- Help explain query-specific timing spikes and uneven optimization benefits in `benchmarking/`.
- Coordinate collection through `experiments/run_query.py`; support `scripts/run_benchmark_batches.sh`.
- Measure the C++ compute unit (CU) on its host. Support both sequential and concurrent execution from the beginning.

## Phase 1 usage and outputs

Rebuild CU and regenerate Python protobufs for the additive clock-anchor/identity fields:

```bash
bash generate_python_proto.sh
cmake --build build --target computeUnit -j2
bash scripts/run_benchmark_batches.sh
```

Configure collection with `benchmark.measure_memory` and the `memory_*` settings in `experiments/configs/benchmark_example.yaml`; the batch script takes no arguments. For an already-running local CU, run `run_query.py` with the same YAML defaults (or override memory settings via its CLI). The runner discovers the CU PID and launch settings automatically; the response PID/hostname must match the sampled process. The batch loop selects execution mode and starts the CU with each dataset scale. Existing timing results remain compatible.

- Options: `--memory-source auto|smaps_rollup|status`, `--memory-interval-ms 20`, `--memory-baseline-ms 500`, `--memory-tail-ms 500`, `--memory-max-gap-ms` (default: five intervals).
- `auto` pilots three `smaps_rollup` reads before collection; selects approximate `status:VmRSS` if a pilot read costs more than 25% of the requested interval or access is unavailable. This is a heuristic, not proof of negligible benchmark overhead. The source remains fixed and is saved in metadata.
- A separate sampling process uses Python `perf_counter_ns` backed by Linux `CLOCK_MONOTONIC`. CU responses provide an explicit operator-clock/monotonic anchor and capture uncertainty. Reject operator mappings outside the submission/response window; preserve native timestamps and the rejection reason.
- Baseline: median of samples during a 500 ms interval after warmup (or configuration if no warmup). This adds one pause before measured rounds, not one pause per round. Final tail is at least two sampling intervals to bracket final responses.
- Collection artifacts beside `results.json`: `memory_samples.csv` (bytes and read timestamps) and `memory_summary.json` (metadata, session/plan/round/tail windows, operators, integrals). `results.json` links them; measured query samples also retain plan IDs. Warmup windows remain marked; measured round numbers match `results.json` and restart at 1 after warmup.
- Integral fields: `integral_mib_seconds`, signed `baseline_integral_mib_seconds`, `average_rss_mib`, and duration. These describe whole-CU RSS during each interval. Invalid coverage produces null integrals with reasons; `sampling_limited` marks windows containing fewer than two samples. Overlapping intervals are not additive.
- Raw CSV is streamed during execution. Collector errors, incomplete plans, and partial data are retained on failures/interruption. Read costs, actual sample spacing, and collector CPU/wall time are recorded. Collection does not import plotting libraries or render figures.
- Render afterward with `python3 scripts/benchmark_plotting/plot_memory.py /path/to/benchmark-session`. Input may also be `results.json` or `memory_summary.json`. New batches under `benchmarking/plots/memory/` contain `memory.png` and a manifest; original measurements remain unchanged. See `scripts/benchmark_plotting/README.md`.
- Tests: `experiments/.venv/bin/python -m unittest discover -s experiments/tests -v`. Quantifying timing perturbation at SF50/SF100 remains an evaluation task on the benchmark host.

## Phase 1: CU memory timeline and integral

Scope: sample whole-CU resident memory and calculate its memory-time integral. Support sequential and concurrent workloads. Allocation/function ownership tracking is deferred.

1. **Target and lifecycle:** pass the CU PID explicitly from the batch launcher to the collector; verify process identity to detect exit/PID reuse. Run collection on the CU host. Start after ingestion/configuration, include warmup and measured rounds, and collect a short configurable tail after final completion. Clean up the collector on success, failure, or interruption.
2. **Source and sampling:** `smaps_rollup` is a kernel-generated virtual file, not a tool. Its `Rss` field is the reference measurement. Pilot configurable 20–50 ms sampling and measure read cost; a full page-table scan may be expensive for large datasets. If needed, use faster approximate `status:VmRSS` samples with occasional detailed snapshots. Select and record the source explicitly; never silently mix sources. Sampling can miss short changes.
3. **Timing:** retain actual read-start/read-end timestamps, use the midpoint as the sample time, and schedule against a monotonic clock. Use actual intervals for integration. Align collector and runner markers explicitly; remote hosts and C++ operator clocks require a clock mapping before overlays are valid.
4. **Boundaries and IDs:** persist session/round IDs, plan IDs, operator IDs and their intervals. Initially summarize client submission-to-response windows on a compatible clock. Obtain samples bracketing each window; interpolate boundaries, flag gaps/incomplete coverage, and avoid unsupported extrapolation. Operator overlays show overlapping activity, not ownership. Do not sum integrals over overlapping windows.
5. **Integral and baseline:** convert Linux `kB` values to bytes (1024 bytes/kB); report MiB and MiB·s. Use trapezoidal integration. Save the absolute curve/integral plus a baseline-relative integral. Choose and record a fixed session baseline from a short quiet interval after configuration/warmup; save per-round starting values to expose drift. Preserve signed differences below baseline. Report duration and average memory alongside the integral.
6. **Cleanup semantics:** response receipt is not cleanup completion. Keep response windows and the post-response tail distinct; a quiet-looking RSS curve does not prove all buffers were freed. Do not add per-round pauses to sustained benchmarks implicitly.
7. **Output and validation:** save raw samples, execution markers, source/interval/baseline metadata, and summaries beside existing benchmark results. Plot CU memory with overlapping execution intervals. Compare sampling-enabled/disabled timings and collection costs; verify units and integration on known constant/ramp traces and handle CU exit, missing samples, and permission errors explicitly.

Interpretation: Phase 1 can report "CU memory during this plan/operator/operation interval." It cannot report memory owned by that code, even if counters are read inside the code. Concurrent workers and earlier surviving allocations contribute to the same RSS. RSS includes resident heap, stack, and mapped pages; it does not identify allocations or memory tiers. Specific-operation overlays would require additional markers.

## Roadmap metrics (retained beyond Phase 1)

| Metric | Purpose |
| --- | --- |
| Memory over time (primary) | Show consumption and allocation lifetimes alongside operator execution. |
| Memory-time integral (MiB·s) | Quantify memory occupancy; report duration and average memory alongside it. |
| Peak memory | Retain as a derived metric per query/operator and concurrent round. |
| Allocation volume and count | Expose allocation churn despite similar live-memory curves. |
| Memory retained after cleanup | Detect accumulation or reuse across rounds. |

- Keep **resident RAM**, **live allocated capacity**, and **logical result size** distinct.
- Record absolute CU memory and the quiescent pre-execution baseline. Integrate baseline-relative CU memory separately from attributed live allocation bytes; baseline subtraction is an estimate, not exact attribution.
- Compute combined peaks from simultaneous live memory; never sum independent query/operator peaks.
- An integral can increase solely because execution takes longer. Memory volume alone does not explain memory-access performance.

## Later: allocation collection and attribution

1. **Always collect CU resident-memory samples** and query/operator execution boundaries. Start with a configurable 10–50 ms sampling interval; measure overhead. Sampled peaks may miss short spikes.
2. **When allocation tracking is implemented, include attribution from its beginning:** session, round, plan, operator, and shared/group IDs; allocation identity, capacity, timestamps, and purpose (base data, shared data, intermediate/output, scratch).
3. Track allocation, resize, ownership transfer, and actual deallocation. Preserve metadata across threads and after operator return. Count shared allocations once; retain producer attribution when buffers become downstream inputs.
4. Cover `Column` buffers, TSL allocations, STL backing storage/hash tables, and direct NUMA allocations. Cover both allocation and adoption paths, including `setDataPtr`; avoid counting the same buffer twice.
5. Derive per-query/operator allocation curves and round-level totals from allocation events. During concurrency, CU RAM is a combined measurement; overlapping time windows cannot establish individual resident-RAM ownership.

## Tooling reference (Phase 1 uses /proc; other tooling is later work)

- **Resident RAM:** Linux `/proc/<cu-pid>/` counters; use `smaps_rollup` for more detailed snapshots, accounting for collection cost. Resident measurements include stack pages and mappings, without function attribution.
- **Allocation attribution:** engine allocation tracking/wrappers or tracking allocators with the IDs above. Track capacity independently of catalog/result sizes.
- **Heaptrack (optional diagnostic):** allocation stacks and lifetimes for an entire session or selected queries. Covers supported heap allocations; stack usage and direct NUMA/mapping allocations need separate coverage. A local `std::vector` can have its object on the stack and its buffer on the heap.
- **`perf stat` (diagnostic):** instructions, cycles, cache misses, page faults, etc.; compare normal and slow executions.
- **`perf record` / `perf report` (diagnostic):** locate CPU-cycle hotspots such as hash build versus probe. **`perf mem`:** investigate costly memory accesses where hardware supports it. These do not directly measure live allocated bytes or RAM footprint.
- **NUMA:** verify actual placement with `numastat -p` / `numa_maps`; distinguish near-memory from far-memory/CXL.
- **Optional cgroup v2:** collect CU footprint, breakdown, and pressure separately from RSS. Launch CU inside it before allocations. Kernel 6.8 has an upstream read-only lifetime `memory.peak`; do not assume per-round reset support.

## Execution and analysis rules

- Keep individual rounds and align memory/allocation events with execution using explicitly compatible timestamps. Python client and C++ server clocks must not be assumed interchangeable.
- Record execution completion, response receipt, and resource cleanup separately. CU currently sends completion before some table cleanup; catalog removal may leave other `shared_ptr` owners alive.
- For isolated-query experiments, establish cleanup before the next measurement. For sustained workloads, retain cleanup overlap as workload behavior.
- Keep warmup policy, query order, scale factor, workers, NUMA placement, build flags, and variant metadata explicit. Save session and per-round baselines to expose drift.
- Run independent sessions with balanced variant order. Existing sessions reuse CU across 20 rounds with zero declared warmup; rounds are not independent process restarts.
- Preserve ordinary timing runs separately from heavier diagnostic profiling. Check collection overhead and allocation-trace coverage before treating measurements as comparable.
- `operator_work` sums operator wall-clock durations: dispatch gaps outside operators are excluded; stalls, page faults, preemption, or internal waits can still extend durations. Increased `operator_work` does not prove extra instructions executed.

## Initial investigations and outputs

- Compare normal/slow rounds and both materialization variants. Existing sequential SF100 unmerged examples: Q4.2 round 5 ≈47.9 s vs ≈38.8 s median; Q3.4 round 15 ≈18.3 s vs ≈14.9 s median. These are timing observations, not evidence of a RAM cause.
- Inspect hash-table/result-buffer lifetimes and the materializing hash join's inner buffer, which overlaps the hash table. Also investigate page faults/reclaim, NUMA locality, cache/bandwidth effects, and scheduling.
- Store raw memory samples, allocation data, execution markers, and per-round summaries with benchmark results.
- Plot memory versus time with operator intervals, variant comparisons, and post-cleanup baseline versus round. Use `perf` diagnostics to explain cases where similar memory footprints have different timings.
