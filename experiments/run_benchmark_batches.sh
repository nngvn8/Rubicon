#!/usr/bin/env bash
# Run in tmux with no grouper or ComputeUnit already running.
set -uo pipefail
# Shared grouper/CU endpoint; the runner discovers it from the CU command line.
readonly IP="127.0.0.1"
readonly PORT=23233
# Runner settings, including memory measurement, come from benchmark_example.yaml.
# Example: bash experiments/run_benchmark_batches.sh
if [[ $# -ne 0 ]]; then
    echo "This script takes no arguments; configure experiments/configs/benchmark_example.yaml." >&2
    exit 2
fi
cd "$(dirname "${BASH_SOURCE[0]}")/.."
logs="$(pwd)/benchmarking/in-batches-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$logs"
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
./build/bin/grouper -port "$PORT" <&3 > "$logs/grouper.log" 2>&1 &
grouper_pid=$!
sleep 2

for pair in "sequential 2" "sequential 50" "sequential 100" "concurrent 2" "concurrent 50" "concurrent 100"; do
    read -r execution_mode sf <<< "$pair"

    sed -i -E \
        -e "s/^(  execution_mode: )[a-z]+/\\1${execution_mode}/" \
        experiments/configs/benchmark_example.yaml

    ./build/bin/computeUnit -ip "$IP" -port "$PORT" \
        -path "data/binary/sf${sf}" -basedata bin -worker 48 -node 0 -cxl_node 1 \
        > "$logs/${execution_mode}-sf${sf}-cu.log" 2>&1 &
    cu_pid=$!

    # Wait for data loading and connection, then allow registration to finish.
    until ss -H -tnp state established "( dport = :$PORT )" | grep -q "pid=$cu_pid,"; do
        if ! kill -0 "$cu_pid" 2>/dev/null; then
            echo "ComputeUnit exited before connecting; see $logs/${execution_mode}-sf${sf}-cu.log" >&2
            exit 1
        fi
        sleep 1
    done
    sleep 2

    (cd experiments && exec uv run python -u run_query.py) \
        > "$logs/${execution_mode}-sf${sf}-queries.log" 2>&1 &
    runner_pid=$!
    # Waiting on a background runner lets signal traps terminate it and its collector.
    wait "$runner_pid"
    runner_status=$?
    runner_pid=""
    if [[ "$runner_status" -ne 0 ]]; then exit "$runner_status"; fi

    kill "$cu_pid"
    wait "$cu_pid"
    cu_pid=""
    sleep 2
done

kill "$grouper_pid"
wait "$grouper_pid"
grouper_pid=""
