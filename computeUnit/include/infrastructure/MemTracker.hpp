#pragma once

// Per-operator RAM tracking (see ram_measurement_per_operator.md).
// Compiled in only with -DRAM_TRACKING=ON; otherwise every function below is an empty stub,
// so call sites never need an #ifdef.

#include <WorkItem.pb.h>
#include <WorkResponse.pb.h>
#include <sys/resource.h>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "tsl.hpp"

namespace memtrack {

#ifdef RAM_TRACKING

// ---------------------------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------------------------

// The operator an allocation belongs to. valid == false means "not inside an operator" (untracked).
struct Owner {
    uint32_t plan = 0;
    uint32_t item = 0;
    bool valid = false;
};

enum class Kind : uint8_t {
    Delta,      // value = +/- bytes of an output buffer (alloc, shrink, free)
    TempLevel,  // value = absolute bytes currently held by the temporaries of this operator
    Dropped     // value = number of events that did not fit into the log (written by flush)
};

// One log entry. 32 bytes, written to the memory log file as raw binary.
struct Event {
    uint64_t t_ns;  // CLOCK_MONOTONIC, same clock as the Python RSS sampler
    uint32_t plan;
    uint32_t item;
    int64_t value;
    Kind kind;
};
static_assert(sizeof(Event) == 32, "Event is written to disk as is, keep its layout stable");

// First 32 bytes of the log file, followed by the raw Event records.
struct FileHeader {
    char magic[8];       // "RUBIMEM1"
    uint32_t version;
    uint32_t eventSize;  // sizeof(Event), lets the reader reject a different layout
    uint64_t capacity;   // slots of the in-memory log
    uint64_t startNs;    // CLOCK_MONOTONIC at init()
};
static_assert(sizeof(FileHeader) == 32, "FileHeader is written to disk as is");
inline constexpr char kMagic[8] = {'R', 'U', 'B', 'I', 'M', 'E', 'M', '1'};
inline constexpr uint32_t kFileVersion = 1;

// Per-thread state. Reset by OperatorScope at the start and end of every operator.
struct ThreadCtx {
    Owner owner;                   // operator currently running on this thread
    uint64_t allocCount = 0;       // number of allocation calls (outputs and temporaries)
    uint64_t requested = 0;        // bytes requested for outputs (capacity, not touched bytes)
    int64_t tempLive = 0;          // bytes held right now by temporary containers
    int64_t tempLogged = 0;        // tempLive at the time of the last snapshot
    std::vector<std::pair<const void*, size_t>> booked;  // outputs allocated but not yet adopted by a Column
};
inline thread_local ThreadCtx ctx;  // one copy per thread

// A temp snapshot is written whenever tempLive moved this far since the last snapshot.
constexpr int64_t kTempDelta = 8 << 20;  // 8 MiB

// ---------------------------------------------------------------------------------------------
// The log (MemTracker.cpp)
// ---------------------------------------------------------------------------------------------

// Allocate and pre-touch the log once at CU start, so it is part of the baseline RSS and never grows.
// Also creates (truncates) the log file at `path` and writes its header.
void init(size_t capacity, const std::string& path);

// Append one event (lock-free). If the log is full the event is dropped and counted.
void record(Owner o, int64_t value, Kind k = Kind::Delta);

// Append the new events to the log file and make room for further ones. Call between rounds.
// Returns the running number of this flush (1, 2, ...), or 0 on failure.
uint64_t flush();

// ---------------------------------------------------------------------------------------------
// Hooks for outputs (buffers that outlive the operator)
// ---------------------------------------------------------------------------------------------

inline Owner currentOwner() { return ctx.owner; }

// Book a freshly allocated output buffer of `bytes` to the running operator.
inline void onAlloc(const void* p, size_t bytes) {
    if (!ctx.owner.valid) return;  // outside an operator: not tracked
    ++ctx.allocCount;
    ctx.requested += bytes;
    ctx.booked.emplace_back(p, bytes);
    record(ctx.owner, +int64_t(bytes));
}

// Book a shrink (realloc to fewer bytes). The block may have moved from `oldp` to `newp`.
inline void onShrink(const void* oldp, const void* newp, size_t newBytes) {
    for (auto& [ptr, bytes] : ctx.booked) {
        if (ptr != oldp) continue;
        if (newBytes < bytes) record(ctx.owner, -int64_t(bytes - newBytes));
        ptr = newp;
        bytes = newBytes;
        return;
    }
}

// A Column takes over the buffer at `p`. Returns the bytes booked for it (0 if it was never booked).
inline size_t adopt(const void* p) {
    for (size_t i = 0; i < ctx.booked.size(); ++i) {
        if (ctx.booked[i].first != p) continue;
        const size_t bytes = ctx.booked[i].second;
        ctx.booked.erase(ctx.booked.begin() + i);
        return bytes;
    }
    return 0;
}

// Book a free to its owner. Runs on any thread (the one that drops the last reference).
inline void onFree(Owner o, size_t bytes) {
    if (!o.valid || bytes == 0) return;
    record(o, -int64_t(bytes));
}

// ---------------------------------------------------------------------------------------------
// Hooks for temporaries (hash table, key copy: born and freed inside one operator)
// ---------------------------------------------------------------------------------------------

// Write a level snapshot if tempLive moved by at least kTempDelta since the last one.
inline void maybeSnapshot() {
    const int64_t moved = ctx.tempLive - ctx.tempLogged;
    if (moved >= kTempDelta || -moved >= kTempDelta) {
        record(ctx.owner, ctx.tempLive, Kind::TempLevel);
        ctx.tempLogged = ctx.tempLive;
    }
}
inline void onTempAlloc(size_t bytes) {
    if (!ctx.owner.valid) return;
    ctx.tempLive += int64_t(bytes);
    ++ctx.allocCount;
    maybeSnapshot();
}
inline void onTempFree(size_t bytes) {
    if (!ctx.owner.valid) return;
    ctx.tempLive -= int64_t(bytes);
    maybeSnapshot();
}

// Std-compatible allocator that reports to the temp counters. Stateless, so all instances are equal.
template <class T>
struct CountingAllocator {
    using value_type = T;
    CountingAllocator() = default;
    template <class U>
    CountingAllocator(const CountingAllocator<U>&) noexcept {}  // needed for rebinding to node/bucket types

    T* allocate(size_t n) {
        onTempAlloc(n * sizeof(T));
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }
    void deallocate(T* p, size_t n) noexcept {
        onTempFree(n * sizeof(T));
        ::operator delete(p);
    }
    template <class U>
    bool operator==(const CountingAllocator<U>&) const noexcept { return true; }
};
template <class T>
using TempAlloc = CountingAllocator<T>;

// ---------------------------------------------------------------------------------------------
// One scope per operator call
// ---------------------------------------------------------------------------------------------

class OperatorScope {
   public:
    explicit OperatorScope(const WorkItem& wi) : faults0_(minorFaults()) {
        ctx = ThreadCtx{};  // fresh counters for this operator
        ctx.owner = {wi.planid(), wi.itemid(), true};
        record(ctx.owner, 0, Kind::TempLevel);  // start snapshot
    }

    // Call after run(): writes the end snapshot and the per-operator numbers into the response.
    void finish(WorkResponse& r) {
        record(ctx.owner, ctx.tempLive, Kind::TempLevel);  // end snapshot, should be 0
        if (!r.has_extendedresult()) return;               // only when the benchmark asked for it
        auto* e = r.mutable_extendedresult();
        e->set_minorfaults(minorFaults() - faults0_);  // x 4096 bytes in the analysis
        e->set_allocationcount(ctx.allocCount);
        e->set_requestedbytes(ctx.requested);
    }

    ~OperatorScope() {
        // Buffers still booked were never adopted by a Column, i.e. freed inside the operator.
        for (const auto& [ptr, bytes] : ctx.booked) onFree(ctx.owner, bytes);
        ctx = ThreadCtx{};  // later work on this thread is not attributed to this operator
    }

   private:
    static uint64_t minorFaults() {
        rusage ru;
        getrusage(RUSAGE_THREAD, &ru);
        return static_cast<uint64_t>(ru.ru_minflt);
    }
    uint64_t faults0_;  // fault counter of this thread at operator start
};

#else  // RAM_TRACKING off: everything compiles to nothing

struct Owner {};
inline void init(size_t, const std::string&) {}
inline uint64_t flush() { return 0; }
inline Owner currentOwner() { return {}; }
inline void onAlloc(const void*, size_t) {}
inline void onShrink(const void*, const void*, size_t) {}
inline size_t adopt(const void*) { return 0; }
inline void onFree(Owner, size_t) {}
template <class T>
using TempAlloc = std::allocator<T>;
struct OperatorScope {
    explicit OperatorScope(const WorkItem&) {}
    void finish(WorkResponse&) {}
};

#endif  // RAM_TRACKING

// ---------------------------------------------------------------------------------------------
// Wrappers for the allocation sites in the operators (valid in both modes)
// ---------------------------------------------------------------------------------------------

// Drop-in for exec.allocate<T>(n, align): additionally books the output buffer.
template <typename T>
T* tracked_allocate(tsl::executor<tsl::runtime::cpu>& exec, size_t n, size_t align = 0) {
    T* p = exec.allocate<T>(n, align);
    onAlloc(p, n * sizeof(T));
    return p;
}

// Shrink an output buffer to newBytes (the usual "worst-case allocation, then cut to the result" pattern).
// realloc(p, 0) would free the block and return NULL, so an empty result keeps a 1-byte block instead.
template <typename T>
T* tracked_shrink(T* p, size_t newBytes) {
    const void* oldp = p;
    void* q = std::realloc(p, newBytes == 0 ? 1 : newBytes);
    T* np = q ? static_cast<T*>(q) : p;  // a failed shrink keeps the old, larger block
    onShrink(oldp, np, newBytes);
    return np;
}

}  // namespace memtrack
