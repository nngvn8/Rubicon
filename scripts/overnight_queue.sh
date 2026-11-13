#!/usr/bin/env bash
# Sequential experiment queue for the SSB 3.x timeout investigation.
# Run a copy from the git-ignored testing/ dir (branch checkouts must not replace the running script):
#   mkdir -p testing/queue && cp scripts/overnight_queue.sh testing/queue/queue.sh && bash testing/queue/queue.sh
# Progress: testing/queue/status.log; per-phase output: testing/queue/out/<phase>.out
set -u

REPO=/home/mschmidt/rubi-test-2/Rubicon
QDIR="$REPO/testing/queue"
mkdir -p "$QDIR/out"
cd "$REPO" || exit 1

export CU_SCRIPT="$REPO/scripts/start_cu_sf.sh"

# Rounds per phase (overridable from the environment); an SF2 restart round takes ~12 s.
R_SF2=${R_SF2:-300}
R_SF2_REUSE=${R_SF2_REUSE:-300}
R_SF50=${R_SF50:-60}
R_SF100=${R_SF100:-25}
R_ASAN=${R_ASAN:-60}

log() { echo "$(date '+%F %T') $*" | tee -a "$QDIR/status.log"; }

# Run test_plans.sh for one phase; args: phase name, SF, extra test_plans.sh args.
run_phase() {
    local name="$1" sf="$2" rc; shift 2
    log "START $name (SF=$sf, args: $*)"
    SF="$sf" bash scripts/test_plans.sh --q q3 --log-cu --log-grouper "$@" > "$QDIR/out/$name.out" 2>&1
    rc=$?
    log "END   $name exit=$rc $(grep -E '^Logs:' "$QDIR/out/$name.out" | tail -n 1)"
    log "SUMMARY $name: $(grep -E 'succeeded' "$QDIR/out/$name.out" | tr '\n' ';')"
}

# Switch superproject and submodule to a branch (objects are local, no network).
checkout_branch() {
    git checkout -q "$1" && git submodule update -q --init || { log "CHECKOUT FAILED $1"; exit 1; }
    git -C ext/SIMDOperators checkout -q "$1"
    log "BRANCH $1 (submodule: $(git -C ext/SIMDOperators rev-parse --short HEAD))"
}

# Debug build (-O0, LOG_DEBUG2) via the repo build script.
build_debug() {
    # Drop the cache so ASan flags from a previous build_asan cannot leak into this build.
    rm -f build/CMakeCache.txt
    bash scripts/build.sh -d 2 > "$QDIR/out/build-debug-$1.out" 2>&1 || { log "BUILD FAILED debug $1"; return 1; }
    log "BUILD ok debug $1"
}

# ASan build into build/ (replaces the Debug binaries).
build_asan() {
    {
        cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DLOG_LEVEL=LOG_DEBUG2 -DGROUPER_VERBOSE=ON -DGROUPER_PROFILING=ON \
            -DCMAKE_CXX_FLAGS="-fsanitize=address -fno-omit-frame-pointer" -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address" &&
        cmake --build build -j"$(nproc)"
    } > "$QDIR/out/build-asan-$1.out" 2>&1 || { log "BUILD FAILED asan $1"; return 1; }
    log "BUILD ok asan $1"
}

# Phase 1: baseline Debug on every scale factor (failures here are the evidence).
checkout_branch sort-timeout-baseline
build_debug baseline && {
    run_phase base-sf2-restart sf2 --runs "$R_SF2" --restart-between-rounds -t 20
    run_phase base-sf2-reuse sf2 --runs "$R_SF2_REUSE" -t 20
    run_phase base-sf50 sf50 --runs "$R_SF50" --restart-between-rounds -t 900
    run_phase base-sf100 sf100 --runs "$R_SF100" --restart-between-rounds -t 1800
}

# Phase 2: ASan on baseline; deterministic detector for the dangling reference.
if build_asan baseline; then
    export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
    run_phase base-asan-sf2 sf2 --runs "$R_ASAN" --restart-between-rounds -t 60
    unset ASAN_OPTIONS
fi

# Phase 3: fix branch, Debug, same SF2 settings as baseline.
checkout_branch sort-timeout-fix
build_debug fix && {
    run_phase fix-sf2-restart sf2 --runs "$R_SF2" --restart-between-rounds -t 20
    run_phase fix-sf2-reuse sf2 --runs "$R_SF2_REUSE" -t 20
}

# Phase 4: fix branch on large scale factors, then leave the fix built for review.
run_phase fix-sf50 sf50 --runs "$R_SF50" --restart-between-rounds -t 900
run_phase fix-sf100 sf100 --runs "$R_SF100" --restart-between-rounds -t 1800
log "QUEUE DONE"
