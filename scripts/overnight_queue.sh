#!/usr/bin/env bash
# Experiment queue for the SSB 3.x timeout investigation (SF2 baseline/fix runs already finished: 0 failures in 900 rounds each).
# Run a copy from the git-ignored testing/ dir so branch checkouts cannot replace the running script:
#   mkdir -p testing/queue && cp scripts/overnight_queue.sh testing/queue/queue.sh && bash testing/queue/queue.sh
# Progress: testing/queue/status.log; per-phase output: testing/queue/out/<phase>.out
set -u

REPO=/home/mschmidt/rubi-test-2/Rubicon
SUB="$REPO/ext/SIMDOperators"
QDIR="$REPO/testing/queue"
mkdir -p "$QDIR/out"
cd "$REPO" || exit 1

export CU_SCRIPT="$REPO/scripts/start_cu_sf.sh"

# Rounds per phase (overridable from the environment).
R_SF50=${R_SF50:-40}
R_SF100=${R_SF100:-15}

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

# Check out a Rubicon branch, then reset the submodule worktree and apply that branch's patches/ (no submodule commits).
use_branch() {
    git checkout -q "$1" || { log "CHECKOUT FAILED $1"; exit 1; }
    git -C "$SUB" checkout -q -- . || { log "SUBMODULE RESET FAILED"; exit 1; }
    local p
    for p in patches/simdoperators-*.patch; do
        git -C "$SUB" apply "$REPO/$p" || { log "PATCH FAILED $p"; exit 1; }
    done
    log "BRANCH $1 (patches: $(ls patches | tr '\n' ' '))"
}

# Debug build (-O0, LOG_DEBUG2) via the repo build script.
build_debug() {
    rm -f build/CMakeCache.txt
    bash scripts/build.sh -d 2 > "$QDIR/out/build-$1.out" 2>&1 || { log "BUILD FAILED $1"; return 1; }
    log "BUILD ok $1"
}

# Phase 1: baseline on the large scale factors, where the failure was observed.
use_branch sort-timeout-baseline
build_debug baseline && {
    run_phase base-sf50 sf50 --runs "$R_SF50" --restart-between-rounds -t 900
    run_phase base-sf100 sf100 --runs "$R_SF100" --restart-between-rounds -t 1800
}

# Phase 2: fix branch with identical settings.
use_branch sort-timeout-fix
build_debug fix && {
    run_phase fix-sf50 sf50 --runs "$R_SF50" --restart-between-rounds -t 900
    run_phase fix-sf100 sf100 --runs "$R_SF100" --restart-between-rounds -t 1800
}

log "QUEUE DONE"
