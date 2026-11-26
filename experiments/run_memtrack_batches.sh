#!/usr/bin/env bash
# Per-operator memory tracking runs: sf 2/50/100, sequential and concurrent (default 10 runs each).
# Uses the RAM_TRACKING build in build-ramtrack/ and the plans from PLAN_SOURCE (default: data/plans).
# Logs and the raw memtrack .bin files go to benchmarking/logs/memtrack-batch-<timestamp>/.
# Run in tmux with no grouper or ComputeUnit of this user already running:
#   bash experiments/run_memtrack_batches.sh
#   RUNS=20 PLAN_SOURCE=pb_plans bash experiments/run_memtrack_batches.sh
set -uo pipefail
readonly IP="127.0.0.1"
readonly PORT=23233   # a grouper of another user may already use 23232
readonly RUNS="${RUNS:-10}"                     # override for a smoke test: RUNS=1 SCALE_FACTORS=2
readonly SCALE_FACTORS="${SCALE_FACTORS:-2 50 100}"
readonly PLAN_SOURCE="${PLAN_SOURCE:-plans}"      # plans (data/plans) or pb_plans (data/pb_plans)
readonly EXECUTION_MODES="${EXECUTION_MODES:-sequential concurrent}"
# CU_DEBUG=1 runs the CU under gdb (batch mode) so a crash leaves a backtrace in <run>-cu.log.
readonly CU_DEBUG="${CU_DEBUG:-0}"
readonly CU_BIN=./build-ramtrack/bin/computeUnit
readonly GROUPER_BIN=./build/bin/grouper
if [[ $# -ne 0 ]]; then
    echo "This script takes no arguments." >&2
    exit 2
fi
cd "$(dirname "${BASH_SOURCE[0]}")/.."
logs="$(pwd)/benchmarking/logs/memtrack-batch-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$logs"

# The label follows the plan set: pb_plans are the unmerged plans, plans the merged ones.
# A copy of the config carries it, so the shared benchmark_example.yaml stays untouched.
case "$PLAN_SOURCE" in
    pb_plans) merged=false; reason="Test late-no-gco plans with materialization outside joins (unmerged, data/pb_plans)" ;;
    plans) merged=true; reason="Test late-no-gco plans with materialization merged into joins (data/plans)" ;;
    *) echo "PLAN_SOURCE must be plans or pb_plans" >&2; exit 2 ;;
esac
config="$logs/benchmark.yaml"
sed -E -e "s|^(  materialize_into_join: ).*|\1${merged}|" -e "s|^(  reason: ).*|\1\"${reason}\"|" \
    experiments/configs/benchmark_example.yaml > "$config"
# Keep console input open; the grouper exits when it receives EOF.
mkfifo "$logs/grouper.stdin"
exec 3<> "$logs/grouper.stdin"
grouper_pid=""
cu_pid=""
runner_pid=""
cleanup() {
    # Disable traps first so cleanup cannot recurse while terminating owned processes.
    trap - EXIT INT TERM
    for pid in "$runner_pid" "$cu_pid" "$grouper_pid"; do
        if [[ -n "$pid" ]]; then kill -TERM "$pid" 2>/dev/null || true; fi
    done
    for pid in "$runner_pid" "$cu_pid" "$grouper_pid"; do
        if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
    done
    exec 3>&-
    rm -f "$logs/grouper.stdin"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$GROUPER_BIN" -port "$PORT" <&3 > "$logs/grouper.log" 2>&1 &
grouper_pid=$!
sleep 2

failed=()
for sf in $SCALE_FACTORS; do
    for execution_mode in $EXECUTION_MODES; do
        run="${execution_mode}-sf${sf}"
        echo "=== $(date +%T) $run ==="
        # Absolute path: the runner finds the file independent of the CU working directory.
        memlog="$logs/${run}-memtrack.bin"

        cu_args=(-ip "$IP" -port "$PORT"
            -path "data/binary/sf${sf}" -basedata bin -worker 48 -node 0 -cxl_node 1
            -memlog "$memlog")
        if [[ "$CU_DEBUG" == 1 ]]; then
            gdb -batch -ex 'handle SIGPIPE nostop noprint pass' -ex 'handle SIGTERM nostop noprint pass' \
                -ex run -ex 'bt 15' -ex 'thread apply all bt 6' \
                --args "$CU_BIN" "${cu_args[@]}" < /dev/null > "$logs/${run}-cu.log" 2>&1 &
            wrapper_pid=$!
            # The CU is a child of gdb; the grouper connection belongs to that pid.
            until cu_pid=$(pgrep -P "$wrapper_pid" -x computeUnit); do sleep 1; done
        else
            "$CU_BIN" "${cu_args[@]}" > "$logs/${run}-cu.log" 2>&1 &
            cu_pid=$!
            wrapper_pid=$cu_pid
        fi

        # Wait for data loading and connection, then allow registration to finish.
        connected=1
        until ss -H -tnp state established "( dport = :$PORT )" | grep -q "pid=$cu_pid,"; do
            if ! kill -0 "$cu_pid" 2>/dev/null; then
                echo "ComputeUnit exited before connecting; see $logs/${run}-cu.log" >&2
                connected=0
                break
            fi
            sleep 1
        done
        if [[ "$connected" -eq 0 ]]; then
            wait "$wrapper_pid" 2>/dev/null
            cu_pid=""
            failed+=("$run (CU)")
            continue
        fi
        sleep 2

        (cd experiments && exec uv run python -u run_query.py --config "$config" \
            --execution-mode "$execution_mode" --runs "$RUNS" --warmup-runs 0 \
            --plan-source "$PLAN_SOURCE" \
            --memtrack --memlog "$memlog") \
            > "$logs/${run}-queries.log" 2>&1 &
        runner_pid=$!
        # Waiting on a background runner lets signal traps terminate it and its collector.
        wait "$runner_pid"
        runner_status=$?
        runner_pid=""
        if [[ "$runner_status" -ne 0 ]]; then
            echo "runner for $run failed with status $runner_status; see $logs/${run}-queries.log" >&2
            failed+=("$run (runner $runner_status)")
        fi

        kill "$cu_pid" 2>/dev/null
        wait "$wrapper_pid"
        cu_status=$?
        # 143 = our SIGTERM; anything else means the CU died on its own (137 SIGKILL/OOM, 139 SIGSEGV, 134 SIGABRT).
        if [[ "$cu_status" -ne 0 && "$cu_status" -ne 143 ]]; then
            echo "ComputeUnit of $run exited with status $cu_status" >&2
            failed+=("$run (CU status $cu_status)")
        fi
        cu_pid=""
        sleep 2
    done
done

kill "$grouper_pid"
wait "$grouper_pid" 2>/dev/null
grouper_pid=""

echo "=== done $(date +%T); logs in $logs ==="
if [[ "${#failed[@]}" -gt 0 ]]; then
    echo "FAILED: ${failed[*]}"
    exit 1
fi
