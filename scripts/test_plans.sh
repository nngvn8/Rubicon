#!/usr/bin/env bash
set -uo pipefail

# ==============================================================================
# Script: test_plans.sh
# Purpose: Run plan batches against Grouper + ComputeUnit (CU), with optional
#          per-query or per-round CU restarts, and report per-plan outcomes.
# ==============================================================================

# --- Paths -------------------------------------------------------------------

# Repository root, resolved relative to this script's location.
RUBICON_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PB_PLANS_DIR="${RUBICON_ROOT}/data/pb_plans"   # Source of all protobuf plans
PLANS_DIR="${RUBICON_ROOT}/data/plans"         # Staging dir filled by --q
EXPERIMENTS_DIR="${RUBICON_ROOT}/experiments"  # Location of run_query.py

# External launchers for the two background services.
GRP_SCRIPT="${GRP_SCRIPT:-${HOME}/start_rubi_grp.sh}"   # Overridable via environment
CU_SCRIPT="${CU_SCRIPT:-${HOME}/start_rubi_cu.sh}"

# --- Option defaults (overridden by the argument parser) ---------------------

TIMEOUT_SECONDS=20              # Per-plan budget; scaled by plan count per batch
VERBOSE=false                   # Dump full run_query.py output per invocation
LOG_CU=false                    # Write CU log to testing/cu-<timestamp>.log
LOG_GROUPER=false               # Write Grouper log to testing/grouper-<timestamp>.log
RESTART_CU=false                # Restart CU after every single plan
RESTART_BETWEEN_ROUNDS=false    # Start a fresh CU at the start of every round
PLAN_SOURCE=pb_plans            # Subdirectory of data/ to run: pb_plans | plans
QUERY_PREFIXES=()               # Filename prefixes selected via --q
CONFIG="${EXPERIMENTS_DIR}/configs/benchmark_example.yaml"
WRITE_BENCHMARK_RESULTS=false   # Persist results under benchmarking/
RUNS=1                          # Measured rounds
WARMUP_RUNS=0                   # Unmeasured rounds executed before measured ones

# ANSI escape sequences for terminal output.
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Print option summary and exit.
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "      --log-cu        Save CU stdout/stderr to testing/cu-<timestamp>.log"
    echo "      --log-grouper   Save Grouper stdout/stderr to testing/grouper-<timestamp>.log"
    echo "  -v, --verbose       Print full output from run_query.py for every test"
    echo "  -t, --timeout <sec> Timeout budget per plan; batches multiply it by plan count (default: 20)"
    echo "  -r, --restart-cu    Restart CU for every plan (default: reuse it)"
    echo "  -b, --benchmark     Write timestamped benchmark results under benchmarking/"
    echo "      --runs <count>   Measured full-batch rounds per benchmark (default: 1)"
    echo "      --warmup-runs <count>  Unmeasured full-batch warmup rounds (default: 0)"
    echo "      --pb_plans       Run all data/pb_plans files (default)"
    echo "      --plans          Run existing data/plans files"
    echo "      --q <q1> ... <qn> Replace data/plans with matching pb_plans prefixes"
    echo "      --restart-between-rounds  Start a fresh CU for each full-batch round"
    echo "  -h, --help          Show this help message"
    exit 0
}

# --- Argument parsing --------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pb_plans|--plans)
            PLAN_SOURCE="${1#--}"
            QUERY_PREFIXES=()
            shift
            ;;
        --q)
            PLAN_SOURCE=plans
            QUERY_PREFIXES=()
            shift
            # Consume all following arguments up to the next option as prefixes.
            while [[ $# -gt 0 && "$1" != -* ]]; do
                QUERY_PREFIXES+=("$1")
                shift
            done
            if [[ ${#QUERY_PREFIXES[@]} -eq 0 ]]; then
                echo "--q requires at least one filename prefix" >&2
                exit 2
            fi
            ;;
        --restart-between-rounds)
            RESTART_BETWEEN_ROUNDS=true
            shift
            ;;
        --log-cu)
            LOG_CU=true
            shift
            ;;
        --log-grouper)
            LOG_GROUPER=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--timeout)
            TIMEOUT_SECONDS="${2:?--timeout requires seconds}"
            shift 2
            ;;
        -r|--restart-cu)
            RESTART_CU=true
            shift
            ;;
        -b|--benchmark)
            WRITE_BENCHMARK_RESULTS=true
            shift
            ;;
        --runs)
            RUNS="${2:?--runs requires a count}"
            shift 2
            ;;
        --warmup-runs)
            WARMUP_RUNS="${2:?--warmup-runs requires a count}"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# --- Process management ------------------------------------------------------

GRP_PID=""   # PID of the backgrounded Grouper launcher pipeline
CU_PID=""    # PID of the backgrounded CU launcher

# Placeholder log paths; replaced by session paths in the logging setup below.
GRP_LOG="/tmp/rubi_grp.log"
CU_LOG="/tmp/rubi_cu.log"

# SIGTERM the tracked CU PID, then any stray computeUnit process by name.
stop_cu() {
    if [[ -n "${CU_PID}" ]] && kill -0 "${CU_PID}" 2>/dev/null; then
        kill -TERM "${CU_PID}" 2>/dev/null || true
    fi
    pkill -f "build/bin/computeUnit" 2>/dev/null || true
    CU_PID=""
    sleep 0.5
}

# SIGTERM the tracked Grouper PID, then any stray grouper process by name.
stop_grouper() {
    if [[ -n "${GRP_PID}" ]] && kill -0 "${GRP_PID}" 2>/dev/null; then
        kill -TERM "${GRP_PID}" 2>/dev/null || true
    fi
    pkill -f "build/bin/grouper" 2>/dev/null || true
    GRP_PID=""
    sleep 0.5
}

# EXIT/INT/TERM handler: stop both services.
cleanup() {
    echo -e "\n${YELLOW}[!] Cleaning up processes...${NC}"
    stop_cu
    stop_grouper
}
trap cleanup EXIT INT TERM

# Launch Grouper in the background; exits the script if it is not running afterwards.
start_grouper() {
    echo -e "${BLUE}[*] Starting Grouper (${GRP_SCRIPT})...${NC}"
    # Kill leftovers from earlier runs.
    stop_grouper
    sleep 1

    # Hold stdin open so Grouper's cin never hits EOF and busy-loops.
    sleep infinity | bash "${GRP_SCRIPT}" > "${GRP_LOG}" 2>&1 &
    GRP_PID=$!
    sleep 1

    # Liveness check by process name; the launcher PID does not identify the binary.
    if ! pgrep -f "build/bin/grouper" >/dev/null; then
        echo -e "${RED}[ERROR] Grouper failed to start. Log output:${NC}"
        cat "${GRP_LOG}"
        exit 1
    fi
}

# Launch CU in the background, appending to CU_LOG; returns 1 if it is not running afterwards.
start_cu() {
    # Kill the previous instance so only one CU runs.
    stop_cu

    bash "${CU_SCRIPT}" >> "${CU_LOG}" 2>&1 &
    CU_PID=$!
    sleep 1

    # Liveness check by process name; the launcher PID does not identify the binary.
    if ! pgrep -f "build/bin/computeUnit" >/dev/null; then
        echo -e "${RED}[ERROR] ComputeUnit failed to start. Log output:${NC}"
        cat "${CU_LOG}"
        return 1
    fi
    return 0
}

# --- Validation and plan staging ---------------------------------------------

# Reject non-numeric counts before touching files or starting services.
if [[ ! "$RUNS" =~ ^[1-9][0-9]*$ || ! "$WARMUP_RUNS" =~ ^[0-9]+$ || ! "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
    echo "--runs and --timeout must be positive integers; --warmup-runs must be nonnegative." >&2
    exit 2
fi

# Fail early if a launcher script is missing.
for SCRIPT in "$GRP_SCRIPT" "$CU_SCRIPT"; do
    if [[ ! -f "$SCRIPT" ]]; then echo "Startup script not found: $SCRIPT" >&2; exit 1; fi
done

# --q: copy pb_plans files matching the prefixes into data/plans.
if [[ ${#QUERY_PREFIXES[@]} -gt 0 ]]; then
    SELECTED_FILES=()

    # nullglob: unmatched globs expand to nothing; dotglob: '*' also matches dotfiles.
    shopt -s nullglob dotglob

    # Resolve every prefix first so a bad prefix aborts before data/plans is cleared.
    for PREFIX in "${QUERY_PREFIXES[@]}"; do
        MATCHES=("${PB_PLANS_DIR}/${PREFIX}"*.pb)
        if [[ ${#MATCHES[@]} -eq 0 ]]; then echo "No plans match prefix: $PREFIX" >&2; exit 2; fi
        SELECTED_FILES+=("${MATCHES[@]}")
    done
    mkdir -p "$PLANS_DIR"

    # Only --q clears data/plans; normal runs leave both plan directories untouched.
    STAGED_FILES=("$PLANS_DIR"/*)
    if [[ ${#STAGED_FILES[@]} -gt 0 ]]; then rm -rf -- "${STAGED_FILES[@]}"; fi
    for PLAN_PATH in "${SELECTED_FILES[@]}"; do cp -- "$PLAN_PATH" "$PLANS_DIR/" || exit 1; done
    shopt -u nullglob dotglob
fi

# --- Plan discovery ----------------------------------------------------------

# Point run_query.py's config at the selected plan source.
sed -i -E "s/^plan_source:.*/plan_source: ${PLAN_SOURCE}/" "$CONFIG" || exit 1
ACTIVE_DIR="${RUBICON_ROOT}/data/${PLAN_SOURCE}"

# Version-sort (q1-2 < q1-10) so batch and per-query modes run plans in the same order.
mapfile -t PLAN_FILES < <(find "$ACTIVE_DIR" -maxdepth 1 -name '*.pb' -type f | sort -V)
TOTAL_PLANS=${#PLAN_FILES[@]}
if [[ "$TOTAL_PLANS" -eq 0 ]]; then echo "No .pb plans found in $ACTIVE_DIR" >&2; exit 1; fi

# --- Logging setup -----------------------------------------------------------

# Per-session directory named by start time; plain mkdir fails if it already exists.
mkdir -p "${RUBICON_ROOT}/testing" || exit 1
LOG_DIR="${RUBICON_ROOT}/testing/plan-tests-$(date +%Y%m%d-%H%M%S)"
mkdir "$LOG_DIR" || exit 1
GRP_LOG="$LOG_DIR/grouper.log"
CU_LOG="$LOG_DIR/cu.log"   # CU restarts append to this same file

# Unique suffix (nanoseconds + PID) for the optional top-level logs.
LOG_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# --log-cu / --log-grouper redirect that service's log to testing/ instead of LOG_DIR.
if [[ "$LOG_CU" == true ]]; then CU_LOG="${RUBICON_ROOT}/testing/cu-${LOG_TIMESTAMP}.log"; fi
if [[ "$LOG_GROUPER" == true ]]; then GRP_LOG="${RUBICON_ROOT}/testing/grouper-${LOG_TIMESTAMP}.log"; fi

# Print log destinations up front so they can be tailed during long runs.
echo "CU output: $CU_LOG"
echo "Grouper output: $GRP_LOG"

# --- Result tracking ---------------------------------------------------------

SUCCESSFUL_PLANS=()   # Labels of runs (batch or single query) that fully succeeded
FAILED_PLANS=()       # Labels of runs that failed, timed out or were incomplete

# Per-plan counters keyed by plan path; also serves as the set of known plan paths.
declare -A QUERY_SUCCESSES=() QUERY_FAILURES=() QUERY_ATTEMPTS=()
for PLAN_PATH in "${PLAN_FILES[@]}"; do
    QUERY_SUCCESSES["$PLAN_PATH"]=0
    QUERY_FAILURES["$PLAN_PATH"]=0
    QUERY_ATTEMPTS["$PLAN_PATH"]=0
done

# Update per-plan counters from one run_query.py log (arg 1).
# A plan counts as started when its path appears alone on a line, and as succeeded
# when the next 'Plan completed successfully.' line follows; started-only means failed.
record_query_results() {
    local output="$1" line current="" plan
    # Sets of plan paths (keys only; value 1 is a placeholder).
    local -A seen=() succeeded=()

    # Pass 1: scan the log and collect started / succeeded plans.
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue

        # Key lookup: is this line a known plan path?
        if [[ -n "${QUERY_ATTEMPTS[$line]+present}" ]]; then
            current="$line"
            seen["$current"]=1
        # Success marker belongs to the most recent plan path.
        elif [[ "$line" == 'Plan completed successfully.' && -n "$current" ]]; then
            succeeded["$current"]=1
            current=""
        fi
    done < "$output"

    # Pass 2: ${!seen[@]} expands to the keys; bump counters per started plan.
    for plan in "${!seen[@]}"; do
        QUERY_ATTEMPTS["$plan"]=$(( ${QUERY_ATTEMPTS["$plan"]} + 1 ))
        if [[ -n "${succeeded[$plan]+present}" ]]; then
            QUERY_SUCCESSES["$plan"]=$(( ${QUERY_SUCCESSES["$plan"]} + 1 ))
        else
            QUERY_FAILURES["$plan"]=$(( ${QUERY_FAILURES["$plan"]} + 1 ))
        fi
    done
}

# Dump all CU thread backtraces to $1 (hang vs spin vs crash); no-op without gdb or a live CU.
capture_cu_diagnostics() {
    local out="$1" pid
    pid="$(pgrep -u "$USER" -f 'build/bin/computeUnit' | head -n 1)"
    if [[ -z "$pid" ]]; then echo "CU not running (crashed or exited)" > "$out"; return 0; fi
    command -v gdb >/dev/null || return 0
    gdb -p "$pid" -batch -ex 'set pagination off' -ex 'thread apply all bt' > "$out" 2>&1 || true
}

# Run run_query.py on one source (directory or .pb file) and record the outcome.
# Args: source, expected plan count, log label. Reads globals IS_WARMUP, VERBOSE.
run_selection() {
    local source="$1" expected="$2" label="$3" status=0 completed
    local args=(--config "$CONFIG" -f "$source" --runs 1 --warmup-runs 0)

    # Warmups and non-benchmark runs skip result and memory collection.
    if [[ "$IS_WARMUP" == true ]]; then
        args+=(--no-write-benchmark-results --no-measure-memory)
    elif [[ "$WRITE_BENCHMARK_RESULTS" == true ]]; then
        args+=(--write-benchmark-results)
    else
        args+=(--no-write-benchmark-results --no-measure-memory)
    fi
    local output="$LOG_DIR/${label}.log"

    # Timeout = per-plan budget x plan count, since the runner blocks for the whole batch.
    (cd "$EXPERIMENTS_DIR" && timeout "$((TIMEOUT_SECONDS * expected))" uv run python -u run_query.py "${args[@]}") > "$output" 2>&1 || status=$?

    # Parse the log even after a timeout so partial progress is still counted.
    record_query_results "$output"

    # -F fixed string, -x whole-line match, -c count.
    completed=$(grep -Fxc 'Plan completed successfully.' "$output" || true)
    if [[ "$status" -eq 0 && "$completed" -eq "$expected" ]]; then
        SUCCESSFUL_PLANS+=("$label")
        echo "[SUCCESS] $label ($completed plans)"
    else
        FAILED_PLANS+=("$label")
        echo "[FAILED] $label (exit $status; $completed/$expected completed); see $output"
        tail -n 10 "$output"
        capture_cu_diagnostics "$LOG_DIR/${label}.cu-stacks.txt"
    fi
    if [[ "$VERBOSE" == true ]]; then cat "$output"; fi
}

# Run every plan as its own invocation, restarting CU after each one.
# File staging stays outside so restarts never move or delete plans.
run_with_query_restarts() {
    local plan

    # Start CU only if none is running; later restarts happen after each query.
    if ! pgrep -f 'build/bin/computeUnit' >/dev/null; then start_cu || return 1; fi
    for plan in "${PLAN_FILES[@]}"; do
        run_selection "$plan" 1 "${ROUND_LABEL}-$(basename "$plan" .pb)"
        # Restart after every query (also after failures and the last query).
        start_cu || return 1
    done
}

# --- Main flow ---------------------------------------------------------------

# Grouper runs for the whole session; the cleanup trap stops it.
start_grouper

# Reuse mode: one CU for all rounds. Otherwise it is started per round inside the loop.
if [[ "$RESTART_BETWEEN_ROUNDS" == false ]]; then start_cu || exit 1; fi
TOTAL_ROUNDS=$((WARMUP_RUNS + RUNS))

for ((ROUND=1; ROUND<=TOTAL_ROUNDS; ROUND++)); do
    # Mutually exclusive with the single initial start above.
    if [[ "$RESTART_BETWEEN_ROUNDS" == true ]]; then start_cu || exit 1; fi

    # Rounds 1..WARMUP_RUNS are warmups; the rest are numbered from 1 as measured.
    IS_WARMUP=false
    ROUND_LABEL="measured-$((ROUND - WARMUP_RUNS))"
    if [[ "$ROUND" -le "$WARMUP_RUNS" ]]; then IS_WARMUP=true; ROUND_LABEL="warmup-$ROUND"; fi
    echo "Running $ROUND_LABEL ($TOTAL_PLANS plans)"

    # Per-query restarts: one invocation per plan. Otherwise: one invocation for the whole directory.
    if [[ "$RESTART_CU" == true ]]; then
        run_with_query_restarts || exit 1
    else
        run_selection "$ACTIVE_DIR" "$TOTAL_PLANS" "$ROUND_LABEL"
    fi
done

# --- Summary -----------------------------------------------------------------

# Counters cover warmups too; plans that were never started show 0/0.
echo "Per-query summary (including warmups):"
for PLAN_PATH in "${PLAN_FILES[@]}"; do
    echo "$(basename "$PLAN_PATH"): succeeded ${QUERY_SUCCESSES[$PLAN_PATH]}/${QUERY_ATTEMPTS[$PLAN_PATH]}, failed ${QUERY_FAILURES[$PLAN_PATH]}/${QUERY_ATTEMPTS[$PLAN_PATH]}"
done

echo "Logs: $LOG_DIR"

# Non-zero exit if any run failed.
if [[ ${#FAILED_PLANS[@]} -gt 0 ]]; then printf 'Failed: %s\n' "${FAILED_PLANS[@]}"; exit 1; fi
exit 0
