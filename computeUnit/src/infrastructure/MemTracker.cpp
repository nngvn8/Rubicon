#include <infrastructure/MemTracker.hpp>

#ifdef RAM_TRACKING

#include <time.h>

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>

namespace memtrack {

namespace {

Event* buf = nullptr;                // the log, allocated once in init()
size_t cap = 0;                      // number of slots, fixed
size_t flushed = 0;                  // slots [0, flushed) are already in the file
std::atomic<size_t> next{0};         // next free slot, handed out to writers lock-free
std::mutex flushMutex;               // only serializes flush() calls, never held by record()

uint64_t nowNs() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ull + static_cast<uint64_t>(ts.tv_nsec);
}

}  // namespace

void init(size_t capacity) {
    cap = capacity;
    buf = static_cast<Event*>(std::malloc(cap * sizeof(Event)));
    if (!buf) {
        std::perror("[memtrack] malloc of the event log failed");
        std::exit(EXIT_FAILURE);
    }
    std::memset(buf, 0, cap * sizeof(Event));  // touch all pages now, so they are part of the baseline RSS
}

void record(Owner o, int64_t value, Kind k) {
    if (!buf) return;  // init() was not called
    const size_t i = next.fetch_add(1, std::memory_order_relaxed);
    if (i >= cap) return;  // log full: never grow, flush() derives the dropped count from `next`
    buf[i] = Event{nowNs(), o.plan, o.item, value, k};
}

bool flush(const std::string& path) {
    std::lock_guard<std::mutex> lock(flushMutex);
    if (!buf) return false;

    FILE* f = std::fopen(path.c_str(), "ab");
    if (!f) return false;

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
    return true;
}

}  // namespace memtrack

#endif  // RAM_TRACKING
