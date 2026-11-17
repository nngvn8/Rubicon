# RAM measurement per operator: methods and decisions

Status: implemented behind `-DRAM_TRACKING=ON` (builds in both modes, not yet run against a workload). Code: `MemTracker.hpp/.cpp`, hooks in `Column.hpp`, `WorkerPool.cpp`, `OperatorDispatcher.cpp`, the operators and `ComputeUnit.cpp` (`-memlog`, `-memlogcap`, `FLUSH_MEMORY_LOG`). Deviation from the sketches: `tracked_allocate` remembers each buffer in a per-thread list, `Column::setDataPtr` adopts it and stores the booked bytes (`trackedBytes`), so bitmask outputs that are not shrunk are freed with the right size. Complements `ram_measurement.md` (plan, Phase 1 RSS timeline) and `ram_measurement_cur_impl.md` (notes on the current Phase-1 code). This file covers **attributing RAM to queries and operators** in the multithreaded compute unit (CU). A glossary is at the bottom.

## 1. Project facts that drive the decisions

- Worker threads are pooled. One worker runs many operators of many plans, and several operators run at once even in "sequential" mode. A thread is not an operator, so every method needs per-thread counters that are read around `op->run()` (`WorkerPool.cpp`).
- Most outputs are allocated with `aligned_alloc(64, ...)` through the tsl executor, some with `malloc`. Many operators allocate for the worst case (for example one slot per input row), write only part of it, then shrink with `realloc` (Filter, HashJoinMat, Materialize, Group).
- Temporary heap structures live only during an operator: the join's `std::unordered_map` (one node per inner key) and key copy, the filter's `result_vec`, sort clusters (`std::deque`), the result operator's `stringstream`.
- Frees are done by whichever thread drops the last reference. Verified on the plans in `data/pb_plans` (q1-1, q3-4, q4-2 decoded with `protoc --decode`): all intermediate columns and the result columns of a plan live in one table `i_<uuid>`; the base tables (`lineorder`, `date`, ...) are only read. `onFinish` calls `dropTable` on that table, on the worker that finished `OP_RESULT`, **after** the plan response was sent. For query groups, the last plan's worker also drops the transferred tables. So frees on a different thread than the allocating one are the normal case.
- Consequence: intermediates are not freed when their last consumer is done but all at once at the end of the plan. A query's memory therefore rises over its run, peaks near the end and falls in one step. An operator's integral is dominated by the time until plan end. Only temporaries (hash table, key copy, `result_vec`) are freed at the end of their operator.
- At SF100 most column-sized buffers are above glibc's maximum `mmap` threshold (32 MiB). They are always fresh from the kernel and returned on free. Smaller buffers come from per-thread arenas and are recycled.
- `numa_alloc_onnode` (direct `mmap`) is used only for base data at ingestion, outside the query window. Base columns are zero-filled at load (`Column::allocate`), so they are already resident.
- Stack is negligible: long-lived workers, no `alloca`, no large local arrays, recursion depth about log n (sort) or string length (LIKE). Well under 100 KiB per worker against GBs of heap.

## 2. What to measure

Three different quantities (also in `ram_measurement.md`):

| Quantity | Source | Meaning |
|---|---|---|
| Result size | `Column::sizeInBytes` after the operator (actual rows x element size); ResultOperator and DataTransfer have no new output column | What the operator logically produces |
| Requested capacity | Size passed to `allocate`/`malloc` (often worst case, e.g. `column->elements`) | How much the operator asked for; result size vs. capacity exposes over-allocation |
| Touched (resident) bytes | Page faults x 4096, RSS | What really occupied RAM |

- Untouched pages of a large buffer have no RAM behind them (overcommit mode 0). Over-allocation is therefore mostly virtual. After `realloc` shrinks a large block, the kernel releases the tail.
- Exception: `Column::allocate()` zero-fills everything, so capacity equals occupancy there.
- Expected gap between requested capacity and result size: large for selective operators. Filters request one slot per input row (`column->elements`), so the ratio is about 1/selectivity (a 2% filter requests about 50x what it writes). Hash joins request `outerElements` slots for two buffers and keep only the matches. Group requests one slot per row and keeps the cluster count. Little or no gap for Map, Sort, Aggregate (one element) and the position-list Materialize (`idx->elements`). The measurement will show the real ratios.
- The relevant metric is **occupancy over time** per operator: when it was touched until when it was freed. Report peak, duration and the MiB*s integral. Record all three quantities above, because their gaps are findings.
- Owner of a buffer = the operator that produced it, until it is freed (even if freed later by another thread or after a consumer read it). Query = plan id, operator = `(planId, itemId)`, group = group id.

## 3. The four methods

| | Core concept | Tools | Data source |
|---|---|---|---|
| **A** minor page faults | Count first touches of pages. Faults x page size = fresh RAM given to the thread | `getrusage(RUSAGE_THREAD).ru_minflt` (simplest), or perf software event `page-faults` (perf-cpp `MultiThreadEventCounter`) | Kernel per-thread fault counter |
| **B** kernel tracepoints | Record each kernel page allocation with its order (size) | perf tracepoints `kmem:mm_page_alloc`, `mm_page_free`; payload recording or eBPF aggregation | Kernel page allocator |
| **C** sampled addresses | Sample the memory addresses a thread accesses, then count unique pages | `perf mem` (perf-cpp `MemoryLoads` on Intel, `IbsOp` on AMD) | CPU hardware sampling (PEBS/IBS) |
| **D** heap allocation tracing | Count requested bytes, live bytes and lifetimes of `malloc`/`free` family calls | In-CU counters, `LD_PRELOAD` wrapper, heaptrack, uprobes/eBPF | Allocator calls (sizes as requested) |

### A: minor page faults
- Fits well: the first write to an output page happens in the operator that allocated it. Counting is per thread and exact (not sampling), so concurrent execution works.
- Per thread only: `getrusage(RUSAGE_THREAD)` is part of glibc (no extra library; perf-cpp is not in the repo) and counts the faults of the calling thread. A fault is charged to the thread that first touches the page, not to the one that called `malloc`. Here the allocating operator writes its own output, so this matches. Faults of helper threads are missed (`TestDataOperator` spawns its own).
- Misses: recycled memory (no fault when the allocator reuses freed memory), all frees, faults on helper threads (`TestDataOperator` spawns its own), kernel-side allocations such as page tables.
- Overcounts: NUMA hint faults (they count as minor faults but give no new memory) and the double fault when a never-written page is read first (zero page, then write fault; negligible here because operators write outputs first and reading already-written pages causes no fault).
- Cold vs. warm: round 1 faults a lot, later rounds less because freed small/medium memory is recycled. Large buffers (>32 MiB) are always fresh, so they are comparable in every round. Keep every round, label round 1 as cold. For a true cold measurement restart the CU (costs a reload of the data).

### B: tracepoints (extends A)
- Same events as A (allocations during a fault happen in the faulting thread), but with the allocation order, so the size per allocation is exact even with huge pages.
- Extra noise: page cache (result `.tsv` writes), page tables, socket buffers, NUMA migration allocations. Frees are batched and happen partly outside CU threads, so per-thread "allocated minus freed" is meaningless.
- Counting mode only gives event counts. For sizes you need payload recording (millions of events) or eBPF aggregation (needs root or `CAP_BPF`/`CAP_PERFMON`).
- Verdict: no benefit here, because THP is `madvise` and A is already exact. Only consider it if THP were `always`.

### C: sampled addresses
- Answers "which memory is accessed", not "which memory is consumed". Dominated by scans of old base data.
- Sampling only: misses short-lived and rarely touched pages. The Intel load event does not see most writes to result buffers (a separate store event exists, with less information). AMD IBS covers loads and stores.
- Same virtual pages can be reused after `munmap`/`mmap`, so unique page numbers mix allocations.
- Useful for NUMA/CXL questions: `data_source` shows local DRAM, remote node or CXL. Keep it as a locality diagnostic, not a RAM metric.

### D: heap allocation tracing
- Frees need `pointer -> (size, owner, time)`. `free(ptr)` only receives a pointer, and the freeing thread knows neither size nor owner.
- With counting inside the CU, no global map is needed for columns: store the owner and size in the `Column`, and `~Column` reports the free (whichever thread runs it). A global map is only needed for malloc-level interception (`LD_PRELOAD`).
- Trace `malloc`, `calloc`, `realloc`, `aligned_alloc`, `posix_memalign` and `free`. `operator new` ends in `malloc`, so tracing the libc layer avoids double counting. Treat `realloc(p, 0)` as a free.
- Limits: sees requested bytes, not RAM. Misses `numa_alloc_onnode`/direct `mmap`, thread stacks, and custom pools. Count shared columns once (the `COMP_NE` alias puts one buffer into two catalog entries).
- Implementation options, cheapest first:

| Option | Gives | Cost | Role |
|---|---|---|---|
| Counters in the CU code (about 25 `allocate` sites, `realloc`, `setDataPtr`, `~Column`) | Exact attribution, because the CU knows the current operator | Negligible | Main approach |
| Counting allocator on chosen containers | Temporaries like the join hash table | Negligible | For the few big temporaries |
| `LD_PRELOAD` wrapper | Every malloc-family call automatically, also STL and protobuf. You still write the wrapper, and the CU must publish the current operator in a thread-local | Small | Only if big temporaries are missed |
| Heaptrack | Call stack for every allocation (where in the code) | Roughly 1.5-3x slowdown | One-off discovery run at smaller scale |
| uprobes via perf/eBPF | The same data (sizes via captured arguments) | Very high: a kernel trap per call (millions of calls for one hash build) | Avoid, it distorts timing |

- Counting allocator: one small reusable class passed as a template parameter. Each container instance then reports its allocations to the current thread's operator counters automatically. The cost is changing the declared type at each container, and containers inside the SIMDOperators library are harder to change. Do it only for the big ones.
- Hash table lifetime: `hash_table` is a local in `doHashJoin`, destroyed when the function returns (same thread, end of the operator). Same for `materializedInner` and `result_vec`.

## 4. Chosen approach: A + D in one record per operator

Per operator and per execution, stored together under `(planId, itemId)`:
- result size, requested capacity, touched bytes (fault delta x 4096), allocation count (number of allocation calls the operator made, a churn indicator: the join hash table alone makes one per inner key),
- peak live bytes, duration live and bytes retained at the end of the operator (its output) are **derived offline** from the event log, not computed at runtime,
- an event log: outputs as events `(timestamp, owner, +/- bytes)`, temporaries as level snapshots `(timestamp, owner, tempLive)` taken by a byte-delta trigger. Small allocations are not logged individually but aggregated, because millions of events would reach hundreds of MB.

How to read A and D together:
- D shows *when* memory is held, as requested capacity (virtual). A shows how much of it became *physically* resident (new pages), but without a time course inside the operator and without frees. Neither is the resident size per operator: D overstates worst-case buffers, A misses recycled memory, so together they bracket it. Temporaries are included in A's per-operator delta (gross), but cannot be told apart from the retained output.
- If touched < requested there are two causes: an unwritten tail (worst-case allocation) or recycled memory. For buffers >32 MiB recycling is impossible, so it is the unwritten tail. For small and medium buffers it is ambiguous.
- For output columns the written part is about the final result size, so touched is roughly known without faults.
- Plots: live capacity per query over time on top of the RSS curve from Phase 1, plus a per-operator table. Check that the sums roughly match RSS.
- Open question, a physical timeline inside operators (details in the subsection "Physical timeline inside operators" below). Why it could matter: D logs an output's capacity as one step at allocation (a join requests about 9.6 GB virtual for 600M outer rows), while the physical memory ramps up as results are written and equals the final size only after the shrink. So D overstates peak and integral during the operator. Why not yet: temporaries are already timed by the snapshots, after the operator D is correct, and the gap is confined to the operator's duration. Decide from the touched/requested ratios of the first measurement. If a timeline is needed, least intrusive first: (1) an external sampler reading per-thread `minflt` from `/proc/<pid>/task/<tid>/stat` every 20 ms, joined offline with the operator intervals (log the thread id in the start/end snapshot), no operator edits; (2) a hook in `View::operator++` (one site, once per chunk of 4M elements) that reads the thread's fault counter and logs it with a byte-delta trigger; (3) no measurement: model the output as a linear ramp from 0 to the final result size over the operator's duration. Limits of any fault timeline: no frees (it never decreases), recycled memory is invisible, and NUMA hint faults appear as spurious touches while base data is scanned. Noise-floor check: run a read-only operator with an empty result, its faults should be near zero. A fourth option, manual fault reads scattered across operators (for example around build and probe), is only worth it if phases must be named, because it needs edits in every operator. Frees do not matter for the fault counter, which never sees them. What limits its accuracy is recycling and NUMA hint faults. Current decision: keep D as logged facts (capacity step, shrink, temp snapshots) plus A per operator, and build any ramp offline as a labeled model (for example linear from 0 to the touched bytes over the operator's duration). Do not bake a model into the logger (for example by logging only the final size at adoption), because the capacity timeline cannot be reconstructed afterwards.

Where the data comes from:
- Rubicon's own objects and counters: `Column` sizes, sizes passed to the allocate sites, plan/item ids from `WorkItem`.
- The kernel fault counter via `getrusage` (before and after `op->run()`).
- RSS from `/proc` (existing Phase 1) as process-level ground truth.
- Clock mapping between Python and C++ already exists (anchors in `PlanResponse`).

Attribution:
- Set a thread-local "current operator" (`planId`, `itemId`) around `op->run()` in the worker loop. Counters add to it.
- Frees are credited to the owner stored in the `Column`, so occupancy falls under the producing operator.
- Per query = sum over its items. Per group via `groupToPlanMapping`. Concurrent queries sum to RSS, but RSS alone cannot split them.

Memory for the records: tiny. About 100 bytes per operator record, and a query has dozens of operators, so kilobytes per round.

Why frees are tracked: occupancy at time t = allocations minus frees up to t. Without frees the curve can only rise. An operator's hash table appears as "+X at start, -X at end", so peak, duration and integral are kept even though the net at the end is zero.

### Physical timeline inside operators (open question, details)

Idea: an operator's thread-local fault counter, read over time, is a cumulative curve of newly touched pages. If the operator frees nothing relevant while it runs, this curve approximates its physical memory growth without the allocation steps of D.

- **Frees inside operators** (checked in the code read so far: Filter, HashJoin and HashJoinMat, Materialize, Sort, Group, Result): outputs are allocated once and only shrunk at the end. The hash table, key copy and `result_vec` are freed when the function returns. Mid-operator frees are small (`std::deque` blocks in the clustering, `stringstream` growth in the result operator). So the curve only rises while the operator runs and steps down at its end, by the temporaries and the released tails. That step is invisible to the fault counter but known from D (temp snapshots, shrink). Offline: physical(t) is roughly faults(t) minus the released bytes. Consistency check: after the operator, physical should be about the result size of its outputs.
- **NUMA hint faults**: reading `numa_hint_faults` from `/proc/vmstat` at the start and end of an operator is system-wide. It isolates an operator only if nothing else runs (one worker, no other busy process). With parallel operators it mixes them. I know of no per-thread hint-fault counter. Options: calibrate in runs with a single worker (hint faults per operator in isolation) and use the noise-floor operator, then treat concurrent numbers as upper bounds.
- **Named phase**: manual fault reads in operator code can carry a label ("after build", "after probe"). A central hook or an external sampler only yields a series of (time, faults), so phases have to be inferred from the shape of the curve and the logged operator intervals.
- **`View::operator++` hook**: `View` is the chunk iterator operators use to walk a column in chunks of 4M elements. Advancing to the next chunk calls `operator++`. A hook there fires once per chunk (about 150 times for a 600M-row column) in every operator that uses `View`, and logs the thread's fault counter with the owner. Limits: only chunked loops produce points. The hash build is not chunked (the inner column is read as one chunk), the probe is. Sort and Group have no chunk loop. The temp snapshots cover the build.
- **External thread sampler**: a sampler outside the operators (it can be added to the Phase-1 collector) reads `minflt` (field 10) from `/proc/<pid>/task/<tid>/stat` of every worker thread, for example every 20 ms. It does not know operators by itself, but a thread runs exactly one operator at a time. If `OperatorScope` logs `(tid, plan, item, start, end)`, the samples of that thread inside the interval are joined offline to the operator. Pitfalls: 20 ms resolution, thread ids change when workers are stopped and started, and one file read per thread per tick (cheap, takes no memory-map lock).
- **Caveats of any fault timeline**: recycled memory is invisible (mainly small and medium memory such as hash-table nodes), hint faults add spurious touches while base data is scanned, and faults of helper threads are missed.

## 5. Preconditions and checks

| Check | Command | Finding on this host |
|---|---|---|
| THP | `cat /sys/kernel/mm/transparent_hugepage/enabled` | `madvise` (active one is in brackets). glibc and the CU do not request huge pages, so pages are 4 KiB. |
| THP really unused | `AnonHugePages` in `/proc/<pid>/smaps_rollup` should be `0 kB` | to verify |
| Multi-size THP (kernels >= 6.8) | `cat /sys/kernel/mm/transparent_hugepage/hugepages-*/enabled` (one line per size, in glob order 1024kB, 128kB, 16kB, 2048kB, 256kB, 32kB, 512kB, 64kB) | None is `always`. All are `never` except 2048kB, which is `inherit` (follows the global `madvise`, so only madvised regions get 2 MiB pages). No effect on the CU. |
| Page size | `getconf PAGESIZE` | 4096 (measured) |
| Faults map to single pages | For anonymous memory without THP one fault gives one page. Exceptions (do not apply): `MAP_POPULATE`/`MADV_POPULATE_WRITE` prefaulting, file-backed fault-around | Holds, since no THP is in effect |
| Other fault kinds | Non-allocating faults: NUMA hint faults, zero page then write (COW), COW after `fork` (the CU never forks). Mapping changes themselves (`munmap`, `mremap` when `realloc` shrinks) cause no faults. Page tables are kernel memory and not counted (about 0.2% of the mapped size). | |
| NUMA balancing | `cat /proc/sys/kernel/numa_balancing` | `1` (hint faults inflate A). No sudo here: record `numa_hint_faults` from `/proc/vmstat` before and after each run/round (system-wide, so valid only if the CU is the main workload) and treat A as an upper bound. |
| Overcommit | `cat /proc/sys/vm/overcommit_memory` | `0` (normal heuristic: untouched allocations cost no RAM) |

Also record in the run metadata: all settings above, round label (cold/warm), whether the CU was restarted.

Optional for more comparable rounds (changes timing, use in separate memory runs): `GLIBC_TUNABLES=glibc.malloc.mmap_threshold=<bytes>` fixes the size above which allocations get their own `mmap` (returned on free, so never recycled) and stops glibc from raising it. `malloc_trim(0)` returns free pool memory to the kernel. Both reduce recycling, but small blocks are still reused.

## 6. Limitations

- Faults give first touches only: no frees, no recycled memory. D gives requested bytes only, not RAM.
- Temporaries outside `Column` need a counting allocator or `LD_PRELOAD`, otherwise they are seen only as faults.
- Per-operator RAM during concurrency cannot be recovered from RSS alone.
- Direct `mmap`, stacks and library-internal pools are not seen by D.
- Changes of the temporary level below one snapshot delta (8 MiB, summed over all counting-allocator containers of one operator) are invisible in the timeline, and the offline peak is only accurate to within one delta. Outputs are always logged. At SF100 a supplier-sized hash table (about 8 MB) sits right at the delta, a 4 MiB delta would show it.
- Response receipt is not cleanup completion (see `ram_measurement.md`).
- Side finding: shrinking with `realloc(ptr, 0)` frees the block and returns `NULL`. The `if (q)` guard then keeps the freed pointer, which `~Column` frees again (double free) when a result is empty. This pattern appears in `FilterOperator.hpp`, `HashJoinOperator*.hpp`, `MaterializeOperator.hpp` and `GroupOperator.cpp`.

## 7. Implementation outline (implemented)

- Central switch: CMake option `RAM_TRACKING` (default OFF, like `GROUPER_VERBOSE`). A header `MemTracker.hpp` provides empty stubs when it is off, so call sites need no `#ifdef`.
- One place for per-operator collection: an RAII `OperatorScope` around `op->run()` in the worker loop (`WorkerPool.cpp`; same wrap in the `SINGLE_CPU_EXEC` path of `OperatorDispatcher.cpp`). It sets the thread-local owner `(planId, itemId)`, snapshots the fault counter and writes the deltas into the `ExtendedResult` (only if the work item has `returnextendedresult`).
- Allocation sites: replace `exec.allocate<T>(n, 64)` by a `tracked_allocate` helper (about 25 one-line changes) and the `realloc` shrink pattern by `tracked_shrink` (about 12 places; also fixes the `realloc(p, 0)` bug).
- Ownership and frees: `Column` records the owner when it takes the buffer (`allocate_aligned_internal`, `setDataPtr`), and `~Column` emits the free event.
- Temporaries: counting allocator on the join hash table (optionally `materializedInner`, `result_vec`). It keeps a running `tempLive` and writes level snapshots with a byte-delta trigger into the log. No per-allocation events and no peak counter (the peak is derived offline).
- Event log timestamps use `CLOCK_MONOTONIC`, the clock of the Python RSS sampler, so no clock mapping is needed. Frees happen after the plan response is sent, so events go to a file or flush point, not into the `PlanResponse`.
- Flush: rounds are independent, so the runner sends a new configuration action at the end of each round and the CU writes the log to a file then. Sustained workloads (no pause between rounds) need a background flusher instead.
- New `ExtendedResult` fields: `minorFaults`, `allocationCount`, `requestedBytes` (regenerate the protobufs as in Phase 1). Peak live, duration and retained bytes are derived offline from the event log.
- Validation: after `clearCatalog`, the tracked live bytes must return to 0.
- Size: about 150 lines of new code plus mechanical edits at the allocate/realloc sites.

### Call paths and why the scope sits where it does

```
Worker pool (default):
  TCP thread: query_plan_cb / work callback -> PlanOrchestrator -> OperatorDispatcher::dispatch
      -> creates the operator, WorkerPool::enqueue_operator   (returns at once, nothing runs here)
  worker thread: UnitWorker loop -> OperatorScope { op->run() } -> onFinish(task)     <- scope here

SINGLE_CPU_EXEC (compile-time alternative, no pool):
  caller -> OperatorDispatcher::dispatch -> OperatorScope { op->run() } -> returns the Task
```

- In the pool build, `dispatch` runs on the TCP thread and only enqueues the operator. The operator itself runs later on a worker. The scope has to sit around the `op->run()` call, because that is the only code that runs on the executing thread.
- The scope must end **before** `onFinish`. `onFinish` sends the response and calls `dropTable`. The frees in `~Column` must be booked to their own owners, not to the operator that happens to be finishing.
- Only one of the two paths is compiled in. `ComputeUnit.cpp` always builds the pool variant of the dispatcher. The `SINGLE_CPU_EXEC` wrap is therefore only there for completeness and is untested.

### `Owner::valid`

- `valid` is true only between the construction and destruction of an `OperatorScope`. Any thread outside an operator has `valid == false`. Examples are base-data ingestion in `main` and transfer columns created on the TCP thread.
- `onAlloc`, `onTempAlloc` and `onFree` return early for an invalid owner. Without the flag, those buffers would be booked to plan 0, item 0. Their frees would then appear without a matching allocation, giving negative occupancy.
- In the `RAM_TRACKING=OFF` build `Owner` is an empty struct and the hooks are empty, so the flag does not exist.

### Flush in detail

- `flush()` runs only on the config action `FLUSH_MEMORY_LOG`. The file is set by the CU option `-memlog` (default `memtrack.bin`) and is created (truncated) with a header in `init`, so one CU process = one file. Nothing sends the action yet: the Python runner has to send it after each round, and the Python protos have to be regenerated.
- The reply text carries a running flush number (`flushed to <path> (flush #N)`), `flush FAILED` on error. The runner uses `N` to tell a reply from a late duplicate of an earlier one (the CU sends every text reply twice).
- `record` writes only into the in-memory buffer. `flush` appends the new events to the file (`"ab"`) after the header that `init` wrote.
- `flushed` is the number of slots from the start of the buffer that are already in the file. `next` is the number of slots handed out so far.
- After writing, the buffer is reset to slot 0 with a compare-and-swap on `next`. If a writer was active in between, for example late frees from `dropTable` after the response, the reset is skipped and the next flush writes the rest.
- If more events arrive than the capacity allows, the surplus is lost. `flush` then appends one `Dropped` event with the number lost, and the offline analysis must check for it.
- The file is a 32-byte header (`magic "RUBIMEM1"`, `version`, `eventSize`, `capacity`, `startNs`) followed by a raw array of 32-byte `Event` structs (`t_ns`, `plan`, `item`, `value`, `kind`). The reader rejects a file whose magic, version or `eventSize` does not match.
- A CU process that serves several runner sessions keeps appending to the same file. The runner therefore drops all events older than its own session start (same clock, `CLOCK_MONOTONIC`).

### Personal notes and Understanding
- One Thread Context (ThreadCtc) object per thread
    - containing
        - allocation count: number of allocations performed
        - allocation bytes: number of bytes requested fo rallocation
        - tempLive: currently allocated bytes held by *temporary* containers
        - Also `owner`, the `(plan, item)` of the operator currently running on this thread.
    - Is initialized and reset by Operator scope
- OperatorScope encloses one operator call
    - Performing Thread Context (ThreadCtx) reset and initalization (Owner and faults_0) upfront
        - faults0_ is initial value of page faults
    - WorkItem enrichment in the end (including fault-delta computation)
    - tracked_allocate, tracked_shrink: wrapper around alloc and realloc using low level helpers to document
    - onAlloc
        - Helper for tacked_allocate
        - increases allocation count, allocation bytes, and adds a record for the number of bytes allocated the point in time
    - onFree
        - Called from `~Column` when an output buffer is freed, often long after the operator ended. A shrink records its own `-(oldBytes - newBytes)` event (the TODO)
        - Not using ctx.owner because `~Column` runs on whichever thread drops the last reference, typically the worker handling `OP_RESULT` in `onFinish` at plan end. Most intermediate columns have been created and are therefore owned by other operators. Therefore for onFree these owners need to be used and not ctx.owner.
    - onTempAlloc
        - Updates allocation data in case of a temporary allocation 
        - updates allocationCount, tempLive and tempPeak
            - Now: updates `allocationCount` and `tempLive`, and writes a snapshot when `tempLive` moved by the byte-delta since the last one. It does not touch `requested`.
    - onTempFree
        - Simlar to onTempAlloc, but does not affect allocationCount
    - record
        - Saves the sample: `(timestamp, plan, item, delta bytes)`
        - used by onAlloc, onFree, onTempAlloc, onTempFree
- Owner
    - Used to document in memory to which operator in which plan (=owner) a change in memory attributes
        - Therefore found in onAlloc, onFree
    - Saved in ThreadCtx (updated by scope for each operator call)
        - Also saved in `Column::owner` when the column takes its buffer. That copy is what `~Column` passes to `onFree`.

### Temporary vs. non-temporary allocations

The split is by **lifetime**, not by size or type. A temporary can be hundreds of MB, and an output can be small.

| | Non-temporary (output buffers) | Temporary (hash table, key copy, `result_vec`) |
|---|---|---|
| Lifetime | Outlives the operator, freed at plan end by another thread | Born and freed inside one `run()` on the same thread |
| Number of allocations | Few (about one or two per output column) | Huge (one per hash-table node, millions) |
| Everything known at operator end? | No, the free comes later | Yes |
| Tracking | One event per allocation, free and shrink, each with an owner | One running counter (`tempLive`) plus level snapshots (byte-delta trigger), no per-allocation events |
| Counted in | `requested`, `allocationCount`, event log | `allocationCount`, level snapshots |

- Outputs need events and an owner because the free happens elsewhere and later, so the occupancy over time spans several operators.
- Temporaries need the level over time, not per-allocation events. At the end of the operator everything is freed, so a plain allocated-minus-freed total would show zero. Events would be unaffordable at millions of allocations, but a snapshot per `kTempDelta` bytes of change is not.
- The peak of an operator (outputs plus temporaries) is computed offline from the timeline: sum the output events and the temp level at each time. Accuracy is within the delta.
- Risk: a buffer allocated with `tracked_allocate` that is freed inside the operator (never adopted by a `Column`) would stay in the books forever. The validation (live bytes return to 0 after `clearCatalog`) catches this.

### Options for temporaries

| # | Option | Gives | Cost / problems |
|---|---|---|---|
| 1 | **Current**: exact counters `tempLive`/`tempPeak`, no log | Exact peak, no timeline (the time of the peak is unknown) | Cheapest. A box event over the operator gives an upper envelope. |
| 2 | **Current + modulo**: also write a level snapshot `(t, owner, tempLive)` on every K-th call. (a) on a call counter, (b) on the pointer (`hash(ptr) % K == 0` in allocate and deallocate, scaled by K) | (a) Timeline with a resolution chosen by K. (b) Sampled real events. | (a) Simple and deterministic, but blind to few huge allocations. (b) Needs no counter, but noisier. |
| 3 | **Current + time**: snapshot if at least T ms passed since the last one | Uniform time resolution | A clock read per call (about 20 ns, millions of calls), or check the clock only every n-th call |
| 4 | **Wrapping with estimation**: `+estimate` after `build_hash_table`, `-estimate` when the function ends (`bucket_count() * 8 + size() * ~32`) | No allocator needed, near-zero cost. Works at phase level. | Depends on the libstdc++ node layout (validate once). Only the end state is known, the ramp is interpolated. |
| 5 | **Wrapping with page faults**: fault delta around the build and probe phase | Physical bytes touched per phase, any granularity | Misses recycled memory, no free information, NUMA hint noise |
| 6 | **Current + byte-delta trigger** (chosen): snapshot whenever `tempLive` moved by at least `kTempDelta` (8 MiB) since the last snapshot | A timeline whose resolution follows the memory change, not the call count. A single huge allocation or free is logged on its own, at construction and at destruction, so no separate large-allocation rule is needed. The number of snapshots is bounded by (bytes allocated and freed) / delta. | One extra field and one comparison per call. Temporaries below the delta stay invisible (only the operator's start and end snapshot, where the level is 0). |

Chosen: option 6, without the runtime peak counter of option 1. The peak and the combination of overlapping operators are derived offline from the snapshots. A single peak value per operator says nothing about the course within an operator, and under concurrency the temporaries of overlapping operators can only be combined correctly if their levels over time are known. Summing peaks gives just an upper bound.


### Cost of snapshots: taking, holding, writing

Estimates, to be confirmed by running the benchmark with `RAM_TRACKING` off and on.

| Part | Estimate | Comment |
|---|---|---|
| Number of events | Hundreds per query, thousands only for large concurrent workloads | Byte-delta: bounded by (bytes allocated and freed) / delta. A hash table of about 100 MB gives about 25 events (8 MiB delta, up and down). Outputs add one to three events per column. |
| Holding | About 32 bytes per event, so about 4 MB for 260 query runs (13 queries x 20 rounds), tens of MB for large concurrent runs | Against tens of GB of resident base data this is about 0.01%. Per-allocation logging (about 6M events, 200 MB) would not be acceptable. |
| Writing | A few KB per query | Written at the end of a round (rounds are independent), so outside any measured time. Sustained workloads need a background flusher. |
| Taking (per event) | About 50 ns | Only hundreds of events per query, so microseconds in total. |
| Checking (per temp call) | A few ns (thread-local counters and one comparison) | Millions of calls give about 10-30 ms on a join that runs 15-48 s, so about 0.1%. Not zero, but small. |

Holding is the critical part, because the buffer could bias the RSS being measured. Design so that it cannot:
- **Preallocate and pre-touch the buffer once at CU start** (for example 2^18 events, 8 MB). Its pages are then part of the baseline RSS and never grow during a run, so there are no reallocation spikes.
- **Fixed capacity, never grows.** The size is chosen once at CU start (for example a startup option). If more events arrive than fit before the next flush, the extra events are discarded and counted in `events_dropped`, which goes into the run metadata. A non-zero count means the timeline of that round is incomplete and the capacity must be raised. The alternative, growing the buffer during the run, would allocate memory in the middle of the measurement and bias exactly the RSS being measured.
- **Append without a lock.** An atomic counter hands out the next free slot, so workers never overwrite each other. The slot then holds the event: timestamp, plan, item, value, kind. The timestamp is the time axis of the timeline and is kept.
- **Write at the end of a round.** Rounds are independent, so the runner triggers the flush between rounds and there is time. Nothing is written during a measured run.
- The log file passes through the page cache, which is kernel memory and not part of the process's RSS. It matters only if you measure through a cgroup (`memory.current` includes page cache). At a few MB it is irrelevant.
- **Validate the overhead**: run the same benchmark built with and without `RAM_TRACKING`. Compare median query times (does tracking slow queries?) and the baseline RSS (it should differ only by the pre-touched buffer). Check `events_dropped == 0`.

Sketches of the buffer, `record` and the flush are in section 8.

## 8. Code sketches (incomplete, for orientation)

**Central switch** (`CMakeLists.txt`)
```cmake
option(RAM_TRACKING "Per-operator memory tracking in computeUnit" OFF)
if(RAM_TRACKING)
    target_compile_definitions(computeUnit PRIVATE RAM_TRACKING)
endif()
```

**`computeUnit/include/infrastructure/MemTracker.hpp`**
```cpp
#pragma once
#include <sys/resource.h>
#include <tsl.hpp>
#include <WorkResponse.pb.h>
#include <WorkItem.pb.h>

namespace memtrack {

#ifdef RAM_TRACKING
struct Owner { uint32_t plan = 0, item = 0; };           // (0,0) = base data / unattributed

enum class Kind : uint8_t { Delta, TempLevel };
struct Event { uint64_t t_ns; uint32_t plan, item; int64_t value; Kind kind; };
// Delta: value = +/- bytes. TempLevel: value = absolute tempLive of that operator.

struct ThreadCtx {
    Owner owner;                  // set by OperatorScope
    uint64_t allocCount = 0, requested = 0;
    int64_t tempLive = 0, tempLogged = 0;   // temp bytes now / at the last snapshot (counting allocator)
};
inline thread_local ThreadCtx ctx;       // global name, one copy per thread

constexpr int64_t kTempDelta = 8 << 20;   // snapshot when tempLive moved by 8 MiB since the last one, adjustable

void record(Owner o, int64_t value, Kind k = Kind::Delta);   // CLOCK_MONOTONIC stamp, append to the sink (=the log: (ti)
// body: see MemTracker.cpp below

inline void onAlloc(size_t bytes) { ++ctx.allocCount; ctx.requested += bytes; record(ctx.owner, +int64_t(bytes)); }
inline void onFree(Owner o, size_t bytes) { record(o, -int64_t(bytes)); }   // any thread

inline void maybeSnapshot() {             // byte-delta trigger, called after every change of tempLive
    if (std::abs(ctx.tempLive - ctx.tempLogged) >= kTempDelta) {
        record(ctx.owner, ctx.tempLive, Kind::TempLevel);
        ctx.tempLogged = ctx.tempLive;
    }
}
inline void onTempAlloc(size_t b) { ctx.tempLive += int64_t(b); ++ctx.allocCount; maybeSnapshot(); }
inline void onTempFree(size_t b)  { ctx.tempLive -= int64_t(b); maybeSnapshot(); }

class OperatorScope {                                    // ONE place for all operators
   public:
    explicit OperatorScope(const WorkItem& wi) : faults0_(minorFaults()) {
        ctx = ThreadCtx{};
        ctx.owner = {wi.planid(), wi.itemid()};
        record(ctx.owner, 0, Kind::TempLevel);           // start snapshot
    }
    void finish(WorkResponse& r) {
        record(ctx.owner, ctx.tempLive, Kind::TempLevel);   // end snapshot (should be 0)
        if (!r.has_extendedresult()) return;             // only when the benchmark asked for it
        auto* e = r.mutable_extendedresult();
        e->set_minorfaults(minorFaults() - faults0_);    // x 4096 in the analysis
        e->set_allocationcount(ctx.allocCount);
        e->set_requestedbytes(ctx.requested);
    }
    ~OperatorScope() { ctx = ThreadCtx{}; }              // later work on this thread is not attributed to this operator
   private:
    static uint64_t minorFaults() { rusage ru; getrusage(RUSAGE_THREAD, &ru); return ru.ru_minflt; }
    uint64_t faults0_;
};

template <class T>
struct CountingAllocator {
    using value_type = T;
    CountingAllocator() = default;
    template <class U> CountingAllocator(const CountingAllocator<U>&) {}   // rebinding to node/bucket types
    T* allocate(size_t n)  { onTempAlloc(n * sizeof(T)); return static_cast<T*>(::operator new(n * sizeof(T))); }
    void deallocate(T* p, size_t n) noexcept { onTempFree(n * sizeof(T)); ::operator delete(p); }
    template <class U> bool operator==(const CountingAllocator<U>&) const { return true; }
};
template <class T> using TempAlloc = CountingAllocator<T>;
#else   // switch off: everything compiles to nothing, call sites stay clean
struct Owner {};
inline void onAlloc(size_t) {}
inline void onFree(Owner, size_t) {}
struct OperatorScope { explicit OperatorScope(const WorkItem&) {} void finish(WorkResponse&) {} };
template <class T> using TempAlloc = std::allocator<T>;
#endif

template <typename T>
T* tracked_allocate(tsl::executor<tsl::runtime::cpu>& exec, size_t n, size_t align = 64) {
    onAlloc(n * sizeof(T));
    return exec.allocate<T>(n, align);
}

// replaces the repeated "realloc shrink, keep old pointer on failure" blocks
template <typename T>
T* tracked_shrink(T* p, size_t oldBytes, size_t newBytes) {
    if (newBytes == 0 || newBytes >= oldBytes) return p;  // avoids realloc(p, 0) == free
    if (void* q = std::realloc(p, newBytes)) p = static_cast<T*>(q);
    // TODO: record(ctx.owner, -int64_t(oldBytes - newBytes)); open: empty result keeps the full block
    return p;
}
}  // namespace memtrack
```

**Worker loop** (`WorkerPool.cpp`, replaces `my_task.response = std::move(my_task.op->run());`; same wrap at `OperatorDispatcher.cpp` in the `SINGLE_CPU_EXEC` path)
```cpp
{
    memtrack::OperatorScope scope(my_task.original_work_item);
    my_task.response = my_task.op->run();
    scope.finish(my_task.response);
}
owning_pool->onFinish(my_task);
```

**Allocation site** (`FilterOperator.hpp`, same pattern in the other sites)
```cpp
// before: intermediate_t* res_ptr = exec.allocate<intermediate_t>(column->elements, 64);
intermediate_t* res_ptr = memtrack::tracked_allocate<intermediate_t>(exec, column->elements, 64);
...
// before: void* q = std::realloc(res_ptr, size_in_bytes); if (q) res_ptr = ...;
res_ptr = memtrack::tracked_shrink(res_ptr, column->elements * sizeof(intermediate_t), size_in_bytes);
```

**`Column`** (the owner is set when the buffer is taken, not at construction: transfer destination columns are constructed on the TCP thread)
```cpp
#ifdef RAM_TRACKING
    memtrack::Owner owner;
#endif
// in allocate_aligned_internal() and setDataPtr():
//     owner = memtrack::ctx.owner;                // the operator running on this thread
// in ~Column(), before the free:
//     memtrack::onFree(owner, sizeInBytes);       // runs on whichever thread drops the last reference
```

**Hash table** (`HashJoinProber.hpp`; usage code is unchanged)
```cpp
template <typename KeyT>
using HashTable = std::unordered_map<KeyT, size_t, std::hash<KeyT>, std::equal_to<KeyT>,
                                     memtrack::TempAlloc<std::pair<const KeyT, size_t>>>;
```

**`MemTracker.cpp`** (the log: preallocated, fixed capacity, flushed at the end of a round)
```cpp
namespace memtrack {
static Event* buf = nullptr;
static size_t cap = 0, flushed = 0;
static std::atomic<size_t> next{0}, dropped{0};

void init(size_t capacity) {                   // at CU start, capacity from a startup option
    cap = capacity;
    buf = static_cast<Event*>(std::malloc(cap * sizeof(Event)));
    std::memset(buf, 0, cap * sizeof(Event));  // touch all pages now, so they are part of the baseline RSS
}

void record(Owner o, int64_t value, Kind k) {
    const size_t i = next.fetch_add(1, std::memory_order_relaxed);   // index of the next free slot
    if (i >= cap) { dropped.fetch_add(1, std::memory_order_relaxed); return; }   // never grows, only counts
    timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    buf[i] = {uint64_t(ts.tv_sec) * 1000000000ull + ts.tv_nsec, o.plan, o.item, value, k};
}

void flush(FILE* f) {      // end of a round: no operator is running
    // fwrite(&buf[flushed], sizeof(Event), min(next, cap) - flushed, f); write `dropped` as well
    // then reset next, flushed and dropped to 0 (late frees from dropTable belong to the next flush if still in flight)
}
}  // namespace memtrack
```

**Flush trigger** (`ComputeUnit.cpp`, in `configAction_cb`; new enum value `FLUSH_MEMORY_LOG` in `ConfigurationRequests.proto`, sent by the runner after each round)
```cpp
} else if (ci.type() == ddd::config::FLUSH_MEMORY_LOG) {
    memtrack::flush(memLogFile);
    response = "[" + prettyName + "] Memory log flushed.";
}
```



## 9. Python side: design draft (not implemented)

Scope: only `experiments/run_query.py` and `utils/memory.py` use the tracking. The other experiment scripts stay untouched. Decisions: the derived data goes into the existing `memory_summary.json` (next to `results.json`, one per run directory), the raw events go next to it as CSV like the RSS samples.

### Data flow

```
CU (RAM_TRACKING)                          runner (run_query.py)                       run directory
 events in RAM  --FLUSH_MEMORY_LOG-->  wait for the ack "flush #N"  -->  CU's -memlog file (header + events)
 ExtendedResult (faults, allocs, bytes) --PlanResponse--> MemorySession.complete_plan
                                           MemorySession.finish: read the file, drop events older than the session
                                             -> memtrack_events.csv   (raw, converted)
                                             -> memory_summary.json   (+ key "operator_tracking")
                                             -> results.json          (existing pointer only)
```

### File structure

```
experiments/
  start_rubi_cu.sh            + -memlog <path> [-memlogcap <n>]
  run_query.py                + --memtrack flag, flush after each round, early HasField check
  proto/*_pb2.py              regenerated with generate_python_proto.sh
  utils/
    util.py                   unchanged (create_configuration_item already works for FLUSH_MEMORY_LOG)
    memory.py                 MemorySession: memlog path, ack-based flush_cu_log(), extra native_operators fields, merge into summary
    memtrack.py               NEW: read events, derive per-operator numbers and per-plan timeline
  tests/
    test_memtrack.py          NEW: synthetic event streams (peak, integral, free-to-zero, dropped)
benchmarking/data/<variant>/<mode>/<run>/
  results.json                unchanged (+ existing results['memory'] pointer)
  memory_summary.json         + "operator_tracking"
  memory_samples.csv          existing RSS samples
  memtrack_events.csv         NEW: raw events (t_ns,plan,item,kind,value)
```

### `run_query.py` (draft)

```python
parser.add_argument('--memtrack', action=argparse.BooleanOptionalAction,
                    default=benchmark_defaults.get('memtrack', False),
                    help='Per-operator memory tracking; needs --measure-memory and a CU built with RAM_TRACKING.')
parser.add_argument('--memlog', default=benchmark_defaults.get('memlog', 'memtrack.bin'),
                    help='Same value as the CU flag -memlog (relative to the CU working directory).')

# after memory.start():
if args.memtrack:
    memory.enable_tracking(args.memlog, client, src_uuid, tgt_uuid)   # resolves the path, registers the reply callback once

# after memory.complete_round(...):
if args.memtrack:
    memory.flush_cu_log()
```

### `memory.py` (draft)

```python
# MemorySession
def enable_tracking(self, memlog: str, client, src_uuid, tgt_uuid):
    # The CU runs on this host (checked via computeUnitHost), so its cwd tells where the relative path lands.
    self.memlog_path = Path(f'/proc/{self.pid}/cwd').resolve() / memlog
    self.tracking = True
    self.session_start_ns = time.perf_counter_ns()      # events older than this belong to an earlier session
    self._client, self._src, self._tgt = client, src_uuid, tgt_uuid
    self._cond = threading.Condition()                  # guards the two fields below
    self._latest_flush = 0                              # highest "flush #N" seen in a CU reply
    self._flush_failed = False
    client.register_callback(TcpPackageType.TEXT, self._on_cu_text)   # once; replaces the default print handler

def _on_cu_text(self, message):
    """Runs on the client's receiver thread whenever a TEXT message arrives, independent of flush_cu_log."""
    text = message.payload.decode()
    print(f'Received Text: {text}')
    found = re.search(r'flushed to .* \(flush #(\d+)\)', text)
    with self._cond:
        if found:
            self._latest_flush = max(self._latest_flush, int(found[1]))
        elif 'flush FAILED' in text:
            self._flush_failed = True
        self._cond.notify_all()                         # wake up flush_cu_log

def flush_cu_log(self, timeout=30):
    with self._cond:
        floor = self._latest_flush                      # a reply only counts if it is newer than this
        self._flush_failed = False
    self._client.send_message(util.create_configuration_item(
        source_uuid=self._src, target_uuid=self._tgt,
        type=ConfigurationRequests.ConfigType.FLUSH_MEMORY_LOG))
    with self._cond:
        # wait_for is the "while not arrived: wait" loop; the receiver thread notifies on every TEXT message.
        # Late duplicates of an earlier reply carry the old number, so they do not satisfy the condition.
        answered = self._cond.wait_for(lambda: self._latest_flush > floor or self._flush_failed, timeout)
    if not answered:
        self.metadata['errors'].append('FLUSH_MEMORY_LOG not acknowledged (CU without RAM_TRACKING?)')
    elif self._flush_failed:
        self.metadata['errors'].append('CU reported: memory log flush failed')

# complete_plan: extra fields per operator (unset when the CU has no tracking)
if self.tracking and any(not i.HasField('minorFaults') for i in response.extendedResults):
    raise RuntimeError('--memtrack set, but the CU sends no tracking data: build it with -DRAM_TRACKING=ON')
window['native_operators'] = [{
    'operator_id': i.itemId, 'start': i.start, 'end': i.end, 'row_count': i.rowCount,
    'minor_faults': i.minorFaults if i.HasField('minorFaults') else None,
    'allocation_count': i.allocationCount if i.HasField('allocationCount') else None,
    'requested_bytes': i.requestedBytes if i.HasField('requestedBytes') else None,
} for i in response.extendedResults]

# finish(): after the tail wait, one more flush for the late frees, then
if self.tracking:
    self.flush_cu_log()
    events = memtrack.load_events(self.memlog_path, since_ns=self.session_start_ns)
    memtrack.write_csv(events, self.directory / 'memtrack_events.csv')
    document['operator_tracking'] = memtrack.derive(events, self.plans)
document['interpretation'] = (
    'windows/operators: whole-CU RSS, integrals of overlapping intervals are not additive. '
    'operator_tracking: requested capacity attributed to the producing operator (virtual, not RSS).')
```

How the wait works: `send_message` returns at once. The reply arrives later on the client's receiver thread, which calls `_on_cu_text`; that is the only code that sees the message. The condition variable is the handoff: `flush_cu_log` sleeps in `wait_for` until the receiver thread has updated `_latest_flush` and called `notify_all`, or until the timeout. Nothing polls, and no state needs resetting between calls because `_latest_flush` only grows. The callback is registered once because it is not tied to a call; it handles every TEXT message for the whole session.

### `memtrack.py` (draft)

```python
import csv, struct
from collections import defaultdict
from pathlib import Path

EVENT = struct.Struct('<QIIqB7x')              # t_ns, plan, item, value, kind (32 bytes, see MemTracker.hpp)
HEADER = struct.Struct('<8sIIQQ')              # magic, version, event_size, capacity, start_ns (32 bytes)
MAGIC, VERSION = b'RUBIMEM1', 1
DELTA, TEMP, DROPPED = 0, 1, 2
MIB = 1024 ** 2

def load_events(path, since_ns=0):
    data = Path(path).read_bytes()
    magic, version, event_size, _capacity, _start = HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION or event_size != EVENT.size:
        raise ValueError(f'{path}: not a memtrack log of this layout')
    body = data[HEADER.size:]
    body = body[:len(body) - len(body) % EVENT.size]   # ignore a torn last record
    # A CU process may serve several sessions; same clock, so older events are simply skipped.
    return [e for e in EVENT.iter_unpack(body) if e[0] >= since_ns]

def write_csv(events, path):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t_ns', 'plan', 'item', 'value', 'kind'])
        w.writerows(events)

def level_steps(delta, temp):
    """Step function of one operator: cumulative output bytes + current temp level."""
    times = sorted({t for t, _ in delta} | {t for t, _ in temp})
    d, tmp, i, j, out = 0, 0, 0, 0, []
    for t in times:
        while i < len(delta) and delta[i][0] <= t: d += delta[i][1]; i += 1
        while j < len(temp) and temp[j][0] <= t: tmp = temp[j][1]; j += 1
        out.append((t, d + tmp, d))                     # (time, total, outputs only)
    return out

def derive(events, plans):
    dropped = sum(v for _, _, _, v, k in events if k == DROPPED)
    owners = defaultdict(lambda: {'delta': [], 'temp': []})
    for t, plan, item, value, kind in events:
        if kind == DELTA: owners[(plan, item)]['delta'].append((t, value))
        elif kind == TEMP: owners[(plan, item)]['temp'].append((t, value))
    operators, per_plan = [], defaultdict(list)
    for (plan, item), o in owners.items():
        steps = level_steps(sorted(o['delta']), sorted(o['temp']))
        if not steps: continue
        # Operator interval = first and last temp snapshot, so no clock alignment is needed.
        start = o['temp'][0][0] if o['temp'] else steps[0][0]
        end = max(t for t, _ in o['temp']) if o['temp'] else steps[0][0]
        area = sum(a[1] * (b[0] - a[0]) for a, b in zip(steps, steps[1:])) / 1e9   # step function: the level is exact between events, no interpolation
        operators.append({
            'plan_id': plan, 'item': item, 'start_ns': start, 'end_ns': end,
            'peak_bytes': max(s[1] for s in steps),
            'integral_mib_seconds': area / MIB,
            'retained_bytes': max((s[2] for s in steps if s[0] <= end), default=0),   # outputs when the operator ended
            'live_bytes_at_plan_end': steps[-1][2],     # output bytes of this operator still live after its last event; 0 once freed
        })
        per_plan[plan].append(steps)
    return {'events': len(events), 'events_dropped': dropped,
            'operators': sorted(operators, key=lambda r: (r['plan_id'], r['item'])),
            'plans': [plan_timeline(p, s) for p, s in per_plan.items()]}

def plan_timeline(plan, step_lists, max_points=2000):
    """Sum of all operators of one plan over time (virtual capacity), thinned for plotting."""
    ...   # merge the step lists on time, keep at most max_points points
```

### `memory_summary.json` outline (new key only)

```json
"operator_tracking": {
  "events": 18234, "events_dropped": 0,
  "operators": [
    {"plan_id": 123, "item": 7, "start_ns": 0, "end_ns": 0,
     "peak_bytes": 0, "integral_mib_seconds": 0.0,
     "retained_bytes": 0, "live_bytes_at_plan_end": 0}
  ],
  "plans": [{"plan_id": 123, "timeline": [[t_ns, bytes]]}]
}
```

The touched/requested numbers stay in `windows[].native_operators` (`minor_faults`, `allocation_count`, `requested_bytes`). Merging by `(plan_id, operator_id)` is done offline in the plotting code.

### Checks the runner must do

- First plan response without `minorFaults` while `--memtrack` is set: abort with "CU not built with RAM_TRACKING".
- `events_dropped > 0`: mark the run invalid, increase `-memlogcap`.
- `live_bytes_at_plan_end != 0` for a plan whose table was dropped: accounting bug or a flush before the late frees, report it.
- Run `--memtrack` and a normal run separately for the overhead comparison (section 7).

## Glossary

| Term | Meaning |
|---|---|
| Virtual / physical memory | A process sees virtual addresses. The kernel assigns physical RAM in 4 KiB pages, only on first touch. |
| Page | 4 KiB unit of memory |
| Minor page fault | The first touch of a page traps into the kernel, which attaches a zeroed page without disk access |
| Heap | Memory requested at run time (`malloc`, `new`, vector contents). Lives until freed, any size, shared by threads. |
| Stack | Per-thread memory for local variables and call frames. Freed on return, small (about 8 MiB limit). |
| Heap shrink | The allocator returns a range to the kernel (`brk` lowered, `munmap`, `madvise`): the process loses the addresses and the pages go back to the kernel's free pool. Memory the allocator keeps stays resident in the process and is reused. |
| Allocator | Library code inside each process (glibc `malloc`), not part of the OS. Talks to the kernel only in whole pages. |
| Arena | A memory pool managed by the allocator. Threads are assigned to arenas. Freed blocks return to the arena they came from, whichever thread frees them. |
| `malloc` / `free` | Request or release heap memory. `new`/`delete` call them. |
| `calloc` | `malloc`, zero-filled |
| `realloc` | Resize a block. Shrinking a big block releases the tail. |
| `aligned_alloc`, `posix_memalign` | `malloc` with an address aligned to a multiple (for example 64 bytes), needed for SIMD |
| `alloca` | Allocate on the stack, freed on return |
| `mmap` / `munmap` | Ask the kernel directly for an address range / give it back |
| `brk` | Grow or shrink the main heap area |
| `madvise` | Hint to the kernel about a memory range (for example `MADV_HUGEPAGE`) |
| RSS | Resident set size: RAM currently held by the process |
| Overcommit | Linux grants allocations beyond free RAM. RAM is only used on touch (mode 0: heuristic). |
| THP | Transparent huge pages: 2 MiB instead of 4 KiB per fault. Modes: always / madvise / never. |
| NUMA | Non-uniform memory access: memory is split into nodes, access to a remote node is slower |
| NUMA hint fault | With `numa_balancing=1` the kernel unmaps pages to learn which node uses them. Counted as minor faults, but give no new memory. |
| `kswapd` | Kernel background thread that frees memory when RAM runs low |
| Tracepoint | Built-in kernel hook that perf can record |
| uprobe | Kernel-assisted breakpoint on a user-space function. Each hit traps into the kernel (slow). |
| eBPF | Small programs that run safely inside the kernel on events |
| PEBS / IBS | CPU hardware for sampling memory accesses (Intel / AMD) |
| `LD_PRELOAD` | Loads your library first so its wrappers run before the real `malloc` and friends (cheap: ordinary function calls) |
| Heaptrack | KDE tool (GitHub) that intercepts allocations and records a call stack for each |
| Counting allocator | A small class passed to a container as template parameter that forwards its allocations to counters |
