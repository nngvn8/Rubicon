#!/usr/bin/env bash
set -euo pipefail

# Resolve Rubicon independently of the caller's working directory.
RUBICON_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEBUG=0

# Parse the supported debug levels; no flag selects Release.
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--debug)
            case "${2-}" in
                1|2) DEBUG="$2"; shift 2 ;;
                *) echo "Usage: $0 [--debug|-d 1|2]" >&2; exit 2 ;;
            esac
            ;;
        *) echo "Usage: $0 [--debug|-d 1|2]" >&2; exit 2 ;;
    esac
done

# Enable unoptimized debug compilation and the selected logging level.
if [[ "$DEBUG" == 1 ]]; then
    # Uncomment (enable) unoptimized debug compilation and comment out optimized build.
    sed -i -E \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O0 -g\).*)$/\1/' \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O3 -g\).*)$/# \1/' \
        "$RUBICON_ROOT/CMakeLists.txt"
    # Build unoptimized and with debug flags.
    cmake -S "$RUBICON_ROOT" -B "$RUBICON_ROOT/build" -DCMAKE_BUILD_TYPE=Debug -DLOG_LEVEL=LOG_DEBUG1 -DGROUPER_VERBOSE=ON -DGROUPER_PROFILING=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    cmake --build "$RUBICON_ROOT/build" -j"$(nproc)"
    # Record compilation metadata only after this build succeeds.
    sed -i -E \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+optimization_level:[[:space:]]*)[^[:space:]#]+/\1-O0/' \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+log_level:[[:space:]]*)[^[:space:]#]+/\1LOG_DEBUG1/' \
        "$RUBICON_ROOT/experiments/configs/benchmark_example.yaml"
elif [[ "$DEBUG" == 2 ]]; then
    # # Uncomment (enable) unoptimized debug compilation and comment out optimized build.
    sed -i -E \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O0 -g\).*)$/\1/' \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O3 -g\).*)$/# \1/' \
        "$RUBICON_ROOT/CMakeLists.txt"
    # Build unoptimized and with debug flags.
    cmake -S "$RUBICON_ROOT" -B "$RUBICON_ROOT/build" -DCMAKE_BUILD_TYPE=Debug -DLOG_LEVEL=LOG_DEBUG2 -DGROUPER_VERBOSE=ON -DGROUPER_PROFILING=ON -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    cmake --build "$RUBICON_ROOT/build" -j"$(nproc)"
    # Record compilation metadata only after this build succeeds.
    sed -i -E \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+optimization_level:[[:space:]]*)[^[:space:]#]+/\1-O0/' \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+log_level:[[:space:]]*)[^[:space:]#]+/\1LOG_DEBUG2/' \
        "$RUBICON_ROOT/experiments/configs/benchmark_example.yaml"
# Restore optimized compilation and reset cached debug settings.
else
    # Uncomment (enable) compiler optimization and comment out (disable)unoptimized build.
    sed -i -E \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O0 -g\).*)$/# \1/' \
        -e 's/^[[:space:]]*#?[[:space:]]*(set\(OPTIMIZE_OPTIONS -O3 -g\).*)$/\1/' \
        "$RUBICON_ROOT/CMakeLists.txt"
    # Build with release flags and optimizations.
    cmake -S "$RUBICON_ROOT" -B "$RUBICON_ROOT/build" -DCMAKE_BUILD_TYPE=Release -DLOG_LEVEL=LOG_INFO -DGROUPER_VERBOSE=OFF -DGROUPER_PROFILING=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    cmake --build "$RUBICON_ROOT/build" -j"$(nproc)"
    # Record compilation metadata only after this build succeeds.
    sed -i -E \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+optimization_level:[[:space:]]*)[^[:space:]#]+/\1-O3/' \
        -e '/^compilation:/,/^[^[:space:]#]/ s/^([[:space:]]+log_level:[[:space:]]*)[^[:space:]#]+/\1LOG_INFO/' \
        "$RUBICON_ROOT/experiments/configs/benchmark_example.yaml"
fi
