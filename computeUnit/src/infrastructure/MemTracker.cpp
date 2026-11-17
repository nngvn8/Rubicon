#include <infrastructure/MemTracker.hpp>

#ifdef RAM_TRACKING

#include <time.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>

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

}  // namespace

void init(size_t capacity, const std::string& path) {
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

void record(Owner o, int64_t value, Kind k) {
    if (!buf) return;  // init() was not called
    const size_t i = next.fetch_add(1, std::memory_order_relaxed);
    if (i >= cap) return;  // log full: never grow, flush() derives the dropped count from `next`
    buf[i] = Event{nowNs(), o.plan, o.item, value, k};
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
            const Event d{nowNs(), 0, 0, static_cast<int64_t>(n - cap), Kind::Dropped};
            std::fwrite(&d, sizeof(Event), 1, f);
        }
        flushed = 0;
    }

    std::fclose(f);
    return ++flushCount;
}

}  // namespace memtrack

#endif  // RAM_TRACKING
