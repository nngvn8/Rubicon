#include <infrastructure/MemTracker.hpp>

#ifdef RAM_TRACKING

#include <time.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <infrastructure/Logger.hpp>
#include <map>
#include <mutex>
#include <string>
#include <vector>

namespace memtrack {

namespace {

Event* buf = nullptr;                // the log, allocated once in init()
size_t cap = 0;                      // number of slots, fixed
size_t flushed = 0;                  // slots [0, flushed) are already in the file
std::atomic<size_t> next{0};         // next free slot, handed out to writers lock-free
std::mutex flushMutex;               // only serializes flush() calls, never held by record()
std::string logPath;                 // file of this CU process, truncated in init()
uint64_t flushCount = 0;             // number of successful flushes, reported to the runner as ack

uint64_t nowNs() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}

// Real chunk size of a `request` byte block, or 0 if it cannot be told.
// Blocks allocated in a row sit one chunk apart, so the most frequent distance is the chunk size.
size_t measureChunk(size_t request) {
    constexpr int kWarmup = 4096;  // used up first: earlier code left freed chunks behind that would be handed out scattered
    constexpr int kBlocks = 256;   // measured: by now they come from fresh heap, next to each other
    std::vector<char*> blocks(kWarmup + kBlocks);
    for (auto& b : blocks) b = static_cast<char*>(::operator new(request));

    std::map<ptrdiff_t, int> distances;  // distance between neighbouring blocks -> how often
    for (size_t i = kWarmup + 1; i < blocks.size(); ++i) ++distances[std::abs(blocks[i] - blocks[i - 1])];
    const auto most = std::max_element(distances.begin(), distances.end(), [](const auto& a, const auto& b) { return a.second < b.second; });
    const bool clear = most->second >= (kBlocks - 1) * 8 / 10;  // a still fragmented heap gives no clear answer

    for (char* b : blocks) ::operator delete(b);
    return clear ? static_cast<size_t>(most->first) : 0;
}

// Check both counting models against the measured chunk sizes, cheapest first.
ChunkMode detectChunkMode() {
    bool formulaHolds = true;
    bool usableHolds = true;
    for (size_t request : {1, 8, 24, 25, 40, 41, 100, 1000}) {
        const size_t measured = measureChunk(request);
        if (measured == 0) return ChunkMode::Requested;
        formulaHolds &= chunkFormula(request) == measured;
        void* p = ::operator new(request);
        usableHolds &= malloc_usable_size(p) + kChunkHeader == measured;
        ::operator delete(p);
    }
    if (formulaHolds) return ChunkMode::Formula;
    if (usableHolds) return ChunkMode::Usable;
    return ChunkMode::Requested;
}

}  // namespace

void init(size_t capacity, const std::string& path) {
    // First, while the heap is still fresh: the measurement needs blocks that sit next to each other.
    chunkMode = detectChunkMode();
    switch (chunkMode) {
        case ChunkMode::Formula:
            LOG_INFO("[memtrack] Temporaries are counted as malloc chunks (computed with formula, verified at start)." << std::endl;)
            break;
        case ChunkMode::Usable:
            LOG_INFO("[memtrack] Temporaries are counted as malloc chunks (malloc_usable_size() + header, verified at start)." << std::endl;)
            break;
        default:
            LOG_WARNING("[memtrack] The malloc chunk size could not be verified: temporaries are counted as requested bytes (a hash table is then about 20% low)." << std::endl;)
    }

    cap = capacity;
    logPath = path;
    buf = static_cast<Event*>(std::malloc(cap * sizeof(Event)));
    if (!buf) {
        std::perror("[memtrack] malloc of the event log failed");
        std::exit(EXIT_FAILURE);
    }
    std::memset(buf, 0, cap * sizeof(Event));  // touch all pages now, so they are part of the baseline RSS

    // One file per CU process: truncate here, flush() only appends.
    FILE* f = std::fopen(logPath.c_str(), "wb");
    if (!f) {
        std::perror("[memtrack] cannot create the memory log file");
        std::exit(EXIT_FAILURE);
    }
    FileHeader h{};
    std::memcpy(h.magic, kMagic, sizeof(h.magic));
    h.version = kFileVersion;
    h.eventSize = sizeof(Event);
    h.capacity = capacity;
    h.startNs = nowNs();
    std::fwrite(&h, sizeof(h), 1, f);
    std::fclose(f);
}

void record(Owner o, int64_t value, Kind k, uint32_t id) {
    if (!buf) return;  // init() was not called
    const size_t i = next.fetch_add(1, std::memory_order_relaxed);
    if (i >= cap) return;  // log full: never grow, flush() derives the dropped count from `next`
    buf[i] = Event{nowNs(), o.plan, o.item, value, k, {}, id};
}

uint64_t flush() {
    std::lock_guard<std::mutex> lock(flushMutex);
    if (!buf) return 0;

    FILE* f = std::fopen(logPath.c_str(), "ab");
    if (!f) return 0;

    const size_t n = next.load(std::memory_order_acquire);  // slots handed out so far (may exceed cap)
    const size_t stored = std::min(n, cap);
    std::fwrite(buf + flushed, sizeof(Event), stored - flushed, f);
    flushed = stored;

    // Reset the log only if no writer was active meanwhile (late frees from dropTable can still arrive).
    // Otherwise the next flush writes the remainder.
    size_t expected = n;
    if (next.compare_exchange_strong(expected, 0)) {
        if (n > cap) {
            const Event d{nowNs(), 0, 0, static_cast<int64_t>(n - cap), Kind::Dropped, {}, 0};
            std::fwrite(&d, sizeof(Event), 1, f);
        }
        flushed = 0;
    }

    std::fclose(f);
    return ++flushCount;
}

}  // namespace memtrack

#endif  // RAM_TRACKING
